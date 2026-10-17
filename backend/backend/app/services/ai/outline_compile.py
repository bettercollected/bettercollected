"""Compile a form outline into one batch of form ops.

Deterministic: the same outline gives the same ops. Everything the outline
asks for becomes typed operations of the ops engine (``ops.py``), with refs
so later ops name what earlier ones create:

- one ``add_page`` per page, its questions inside (refs ``p.<key>`` and
  ``q.<key>``), then ``set_section_title`` per page that has one;
- ``set_field_validation`` for answer limits;
- ``set_field_logic`` per show/hide rule and ``set_page_jumps`` per page
  with jumps (``"end"`` submits);
- ``set_theme_preset`` when the outline names another look than Leaflet,
  the default every new form starts with (in the preset's own style, else
  the classic one).

``build_form`` applies the batch atomically to a blank form (welcome page,
one ending, Leaflet) in memory; the caller saves the result once.
"""

from typing import Any, Dict, List, Optional, Tuple

from common.models.standard_form import (
    LayoutType,
    StandardForm,
    ThankYouPageField,
    WelcomePageField,
)

from backend.app.constants.themes import (
    NEW_FORM_THEME,
    new_form_theme,
    preset_name,
    themes as THEME_PRESETS,
)
from backend.app.services.ai.ops import (
    JUMP_TARGET_SUBMIT,
    OpResult,
    apply_form_ops,
    parse_ops,
)
from backend.app.services.ai.outline import (
    CHOICE_TYPES,
    END,
    NUMERIC_TYPES,
    TEXT_TYPES,
    FormOutline,
    OutlineCondition,
    OutlineQuestion,
    _distinct,
    _number,
    _yes_no_value,
    needs_choices,
)

FIELD_TYPES = {"statement": "text"}
COMPARISON_OPS = {
    "equals": "IS_EQUAL",
    "not_equals": "IS_NOT_EQUAL",
    "contains": "CONTAINS",
    "not_contains": "DOES_NOT_CONTAIN",
    "is_answered": "IS_NOT_EMPTY",
    "is_not_answered": "IS_EMPTY",
    "greater_than": "GREATER_THAN",
    "less_than": "LESS_THAN",
    "at_least": "GREATER_THAN_EQUAL",
    "at_most": "LESS_THAN_EQUAL",
}


def page_ref(key: str) -> str:
    return f"p.{key}"


def question_ref(key: str) -> str:
    return f"q.{key}"


def _ref(name: str) -> str:
    return f"$ref:{name}"


def without_unfillable_choices(outline: FormOutline) -> Tuple[FormOutline, List[str]]:
    """A choice question still without two choices cannot be built as one:
    it is asked as short text instead, with a note."""
    changed = 0
    result = outline.model_copy(deep=True)
    for page in result.pages:
        for question in page.questions:
            if needs_choices(question):
                question.type = "short_text"
                question.choices = None
                question.allow_multiple = None
                changed += 1
    notes = (
        [f"{changed} choice question(s) without choices are asked as short text."]
        if changed
        else []
    )
    return result, notes


def _field_spec(question: OutlineQuestion) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "title": " ".join(question.label.split()),
        "type": FIELD_TYPES.get(question.type, question.type),
        "ref": question_ref(question.key),
    }
    if question.type != "statement":
        spec["required"] = bool(question.required)
    if question.description and question.description.strip():
        spec["description"] = question.description.strip()
    if question.why_we_ask and question.why_we_ask.strip():
        spec["whyWeAsk"] = " ".join(question.why_we_ask.split())
    if question.type in CHOICE_TYPES:
        spec["choices"] = _distinct(question.choices)
        if question.type == "multiple_choice" and question.allow_multiple:
            spec["allowMultiple"] = True
    return spec


def _validation(question: OutlineQuestion) -> Optional[Dict[str, Any]]:
    """The answer limits that apply to the question's type; others are left
    out rather than failing the batch."""
    rules = question.validation
    if rules is None:
        return None
    patch: Dict[str, Any] = {}
    if question.type in TEXT_TYPES:
        if rules.min_length is not None:
            patch["minLength"] = rules.min_length
        if rules.max_length is not None:
            patch["maxLength"] = rules.max_length
        if (
            "minLength" in patch
            and "maxLength" in patch
            and patch["minLength"] > patch["maxLength"]
        ):
            patch.pop("minLength")
        if rules.preset and question.type == "short_text":
            patch["preset"] = rules.preset
    if question.type == "number":
        if rules.min_value is not None:
            patch["minValue"] = rules.min_value
        if rules.max_value is not None:
            patch["maxValue"] = rules.max_value
        if (
            "minValue" in patch
            and "maxValue" in patch
            and patch["minValue"] > patch["maxValue"]
        ):
            patch.pop("minValue")
    return patch or None


def _condition(
    condition: OutlineCondition, questions: Dict[str, OutlineQuestion]
) -> Dict[str, Any]:
    source = questions[condition.question]
    spec: Dict[str, Any] = {
        "fieldId": _ref(question_ref(condition.question)),
        "comparison": COMPARISON_OPS[condition.comparison],
    }
    if condition.comparison in ("is_answered", "is_not_answered"):
        return spec
    value: Any = " ".join((condition.value or "").split())
    if source.type == "yes_no":
        value = _yes_no_value(value)
    elif source.type in CHOICE_TYPES:
        # the choice's own spelling: conditions compare choice labels
        labels = {c.lower(): c for c in _distinct(source.choices)}
        value = labels.get(value.lower(), value)
    elif source.type in NUMERIC_TYPES and _number(value) is not None:
        number = _number(value)
        value = int(number) if number.is_integer() else number
    spec["value"] = value
    return spec


def compile_outline(outline: FormOutline) -> List[Dict[str, Any]]:
    """The ops that build ``outline`` on a blank form. The outline must be
    one ``prune_outline`` and ``without_unfillable_choices`` passed."""
    questions = {q.key: q for _, q in outline.questions()}
    ops: List[Dict[str, Any]] = []
    for page in outline.pages:
        ops.append(
            {
                "op": "add_page",
                "ref": page_ref(page.key),
                "fields": [_field_spec(q) for q in page.questions],
            }
        )
    for page in outline.pages:
        title = " ".join((page.section_title or "").split())
        if title:
            ops.append(
                {
                    "op": "set_section_title",
                    "pageId": _ref(page_ref(page.key)),
                    "title": title,
                }
            )
    for _, question in outline.questions():
        patch = _validation(question)
        if patch:
            ops.append(
                {
                    "op": "set_field_validation",
                    "fieldId": _ref(question_ref(question.key)),
                    "validation": patch,
                }
            )
    for rule in outline.logic:
        ops.append(
            {
                "op": "set_field_logic",
                "fieldId": _ref(question_ref(rule.target)),
                "logic": {
                    "action": rule.action.upper(),
                    "operator": "AND" if rule.match == "all" else "OR",
                    "conditions": [_condition(c, questions) for c in rule.conditions],
                },
            }
        )
    jumps_by_page: Dict[str, List[Dict[str, Any]]] = {}
    for jump in outline.jumps:
        jumps_by_page.setdefault(jump.from_page, []).append(
            {
                "operator": "AND" if jump.match == "all" else "OR",
                "conditions": [_condition(c, questions) for c in jump.conditions],
                "target": (
                    JUMP_TARGET_SUBMIT if jump.to == END else _ref(page_ref(jump.to))
                ),
            }
        )
    for page in outline.pages:
        if page.key in jumps_by_page:
            ops.append(
                {
                    "op": "set_page_jumps",
                    "pageId": _ref(page_ref(page.key)),
                    "jumps": jumps_by_page[page.key],
                }
            )
    theme = preset_name(outline.theme)
    if theme and theme != NEW_FORM_THEME:
        # the preset's own style, else the plain one (not the Leaflet style
        # the blank form starts with): another look was asked for
        ops.append(
            {
                "op": "set_theme_preset",
                "name": theme,
                "style": THEME_PRESETS[theme].style or "classic",
            }
        )
    return ops


def blank_form(outline: FormOutline) -> StandardForm:
    """What the ops start from: title, welcome page, one ending, Leaflet."""
    title = " ".join(outline.title.split())
    description = (outline.description or "").strip() or None
    return StandardForm(
        title=title,
        description=description,
        builder_version="v2",
        theme=new_form_theme(),
        welcome_page=WelcomePageField(
            title=title,
            description=description,
            layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND,
        ),
        thankyou_page=[
            ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)
        ],
        fields=[],
    )


def theme_note(outline: FormOutline) -> List[str]:
    if outline.theme and not preset_name(outline.theme):
        return ["The requested look is not a theme preset; the form uses Leaflet."]
    return []


def build_form(outline: FormOutline) -> Tuple[StandardForm, List[OpResult]]:
    """The form the outline describes, built atomically through the ops
    engine: when any op fails, the blank form comes back with every
    result (``applied(results, atomic=True)`` is False)."""
    ops = parse_ops(compile_outline(outline))
    return apply_form_ops(blank_form(outline), ops, atomic=True)
