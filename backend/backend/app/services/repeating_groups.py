"""Repeating groups: server-side checks of submitted group answers.

A repeating group is a ``group`` field with ``properties.repeat`` whose child
questions respondents fill once per item. The answer is stored under the
group id as ``{"type": "group", "items": [{<child id>: <answer>}, ...]}``.

The webapp enforces the same rules while the form is filled
(``webapp/src/utils/repeating-groups.ts``); these checks make sure a crafted
submission cannot store more (or fewer) items than the creator allowed, or
skip a required question of an item. Visibility rules inside an item are
evaluated with the item's own answers, exactly like the webapp does, so a
child hidden by logic is never required.

Groups hidden by logic or on pages skipped by a jump submit no answer at all;
a missing group answer is therefore accepted here, but a submitted one must
respect the limits. (``answer_validation`` replays page navigation and checks
the required questions of the items a group shows on the respondent's path.)
"""

from typing import Any, Dict, Iterable, List, Optional

from common.expressions import format_expression_value
from common.models.standard_form import (
    StandardForm,
    StandardFormFieldType,
    StandardFormResponseAnswer,
)
from pydantic import BaseModel, ValidationError

GROUP = StandardFormFieldType.GROUP.value


def _type_value(field_type: Any) -> Optional[str]:
    return getattr(field_type, "value", field_type)


def _as_dict(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


def iter_repeating_groups(form: StandardForm) -> Iterable[Any]:
    """Yield every repeating group field of a v2 form (groups live on pages)."""
    for slide in form.fields or []:
        for field in (slide.properties.fields if slide.properties else None) or []:
            if (
                _type_value(field.type) == GROUP
                and field.properties is not None
                and field.properties.repeat is not None
            ):
                yield field


def comparable_answer_value(answer: Any, field_type: Optional[str]) -> Any:
    """Python twin of the webapp's ``getComparableAnswerValue``."""
    answer = _as_dict(answer)
    if not isinstance(answer, dict):
        return None
    if field_type == "yes_no":
        value = answer.get("boolean")
        return ("Yes" if value else "No") if isinstance(value, bool) else None
    if field_type in ("short_text", "long_text"):
        return answer.get("text")
    if field_type == "email":
        return answer.get("email") or answer.get("text")
    if field_type == "url":
        return answer.get("url") or answer.get("text")
    if field_type in ("number", "rating", "linear_rating"):
        return answer.get("number")
    if field_type == "date":
        return answer.get("date")
    if field_type == "phone_number":
        return answer.get("phoneNumber") or answer.get("phone_number")
    if field_type == "calculated":
        # the server's stored value (services/calculated_fields.py), as the
        # plain text the expressions spec prints: 12.5, "true", a text
        for slot in ("number", "boolean", "text"):
            if answer.get(slot) is not None:
                return format_expression_value(answer[slot])
        return None
    if field_type in ("multiple_choice", "dropdown"):
        choices = answer.get("choices") or {}
        if isinstance(choices, dict) and choices.get("values") is not None:
            return choices.get("values")
        choice = answer.get("choice") or {}
        return choice.get("value") if isinstance(choice, dict) else None
    return answer.get("text", answer.get("value"))


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, list) and not value)


def _to_number(value: Any) -> float:
    try:
        return float(value)
    except OverflowError:
        # an integer too big for a float: JavaScript's Number makes it Infinity
        return float("inf") if value > 0 else float("-inf")
    except (TypeError, ValueError):
        return float("nan")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def compare(value: Any, comparison: Optional[str], target: Any) -> bool:
    """Python twin of the webapp comparison switch (``evaluateCondition``)."""
    if comparison == "IS_EMPTY":
        return _is_empty(value)
    if comparison == "IS_NOT_EMPTY":
        return not _is_empty(value)
    if comparison in ("IS_EQUAL", "CONTAINS", "IS_NOT_EQUAL", "DOES_NOT_CONTAIN"):
        negate = comparison in ("IS_NOT_EQUAL", "DOES_NOT_CONTAIN")
        if isinstance(value, list):
            hit = _text(target) in [str(v) for v in value]
        elif comparison in ("IS_EQUAL", "IS_NOT_EQUAL"):
            hit = _text(value) == _text(target)
        else:
            hit = _text(target).lower() in _text(value).lower()
        return not hit if negate else hit
    if comparison in (
        "GREATER_THAN",
        "GREATER_THAN_EQUAL",
        "LESS_THAN",
        "LESS_THAN_EQUAL",
    ):
        if isinstance(value, list):
            return False
        left, right = _to_number(value), _to_number(target)
        if comparison == "GREATER_THAN":
            return left > right
        if comparison == "GREATER_THAN_EQUAL":
            return left >= right
        if comparison == "LESS_THAN":
            return left < right
        return left <= right
    if comparison == "STARTS_WITH":
        return _text(value).lower().startswith(_text(target).lower())
    if comparison == "ENDS_WITH":
        return _text(value).lower().endswith(_text(target).lower())
    return False


def group_items(answer: Any) -> List[Dict[str, Any]]:
    answer = _as_dict(answer)
    items = answer.get("items") if isinstance(answer, dict) else None
    return (
        [i if isinstance(i, dict) else {} for i in items]
        if isinstance(items, list)
        else []
    )


def logic_sources(fields: Any) -> Dict[str, Any]:
    """The questions of a form by id (page questions and the questions of
    groups), where a condition on a choice question reads its options.
    ``fields``: the form's top-level fields (its pages). Twin of the
    webapp's ``logicSourcesById``."""
    by_id: Dict[str, Any] = {}

    def add(field: Any) -> None:
        if getattr(field, "id", None):
            by_id[str(field.id)] = field

    for top in fields or []:
        props = getattr(top, "properties", None)
        for field in (getattr(props, "fields", None) if props else None) or []:
            add(field)
            if _type_value(field.type) == GROUP and field.properties is not None:
                for child in field.properties.fields or []:
                    add(child)
    return by_id


CHOICE_TYPES = ("multiple_choice", "dropdown")
NEGATED_COMPARISONS = ("IS_NOT_EQUAL", "DOES_NOT_CONTAIN")


def _filled_text(value: Any) -> bool:
    """A string or number to compare (JavaScript's ``filledText``)."""
    if isinstance(value, bool):
        return False
    return (isinstance(value, str) and value != "") or isinstance(value, (int, float))


def _choice_tokens(chosen: str, source: Any) -> List[str]:
    """What a chosen option answers to: its id, its text and its label (an
    unknown id: itself)."""
    props = getattr(source, "properties", None) if source is not None else None
    for choice in (getattr(props, "choices", None) if props else None) or []:
        choice = _as_dict(choice)
        if isinstance(choice, dict) and choice.get("id") == chosen:
            tokens: List[str] = []
            for token in (chosen, choice.get("value"), choice.get("label")):
                if _filled_text(token) and _text(token) not in tokens:
                    tokens.append(_text(token))
            return tokens
    return [chosen]


def _evaluate_choice_condition(
    answer: Any, source: Any, comparison: Optional[str], target: Any
) -> bool:
    """A condition on a choice question. The answer holds option ids (and
    the text typed as "Other"); the condition names an option by its text or
    its id. Twin of the webapp's ``evaluateChoiceCondition``."""
    answer = _as_dict(answer)
    answer = answer if isinstance(answer, dict) else {}
    many = _as_dict(answer.get("choices"))
    if isinstance(many, dict):
        values = many.get("values")
        tokens = [
            token
            for value in (values if isinstance(values, list) else [])
            if _filled_text(value)
            for token in _choice_tokens(_text(value), source)
        ]
        if _filled_text(many.get("other")):
            tokens.append(_text(many["other"]))
        return compare(tokens, comparison, target)
    one = _as_dict(answer.get("choice"))
    one = one if isinstance(one, dict) else {}
    tokens = (
        _choice_tokens(_text(one["value"]), source)
        if _filled_text(one.get("value"))
        else []
    )
    if _filled_text(one.get("other")):
        tokens.append(_text(one["other"]))
    if not tokens:
        return compare(None, comparison, target)
    results = [compare(token, comparison, target) for token in tokens]
    return all(results) if comparison in NEGATED_COMPARISONS else any(results)


def evaluate_condition(
    answers: Dict[str, Any],
    condition: Any,
    sources: Optional[Dict[str, Any]] = None,
) -> bool:
    condition = _as_dict(condition) or {}
    get = lambda snake, camel: condition.get(snake, condition.get(camel))  # noqa: E731
    field_id = get("field_id", "fieldId")
    group_mode = get("group_mode", "groupMode")
    comparison = condition.get("comparison")
    target = condition.get("value")
    if group_mode:
        items = group_items(answers.get(field_id))
        if group_mode == "COUNT":
            return compare(len(items), comparison, target)
        child = {
            "field_id": get("child_field_id", "childFieldId"),
            "field_type": get("child_field_type", "childFieldType"),
            "comparison": comparison,
            "value": target,
        }
        if not child["field_id"]:
            return False
        matches = [
            evaluate_condition({**answers, **item}, child, sources) for item in items
        ]
        if group_mode == "ANY":
            return any(matches)
        if group_mode == "ALL":
            return bool(matches) and all(matches)
        return False
    field_type = get("field_type", "fieldType")
    if field_type in CHOICE_TYPES:
        return _evaluate_choice_condition(
            answers.get(field_id), (sources or {}).get(field_id), comparison, target
        )
    value = comparable_answer_value(answers.get(field_id), field_type)
    return compare(value, comparison, target)


def evaluate_conditions(
    operator: Optional[str],
    conditions: Any,
    answers: Dict[str, Any],
    sources: Optional[Dict[str, Any]] = None,
) -> bool:
    """Fold conditions with AND/OR. ``sources``: the form's questions by id
    (``logic_sources``), which a condition on a choice question needs to
    match an option's text; without it, only option ids match."""
    valid = [
        c
        for c in (_as_dict(c) for c in (conditions or []))
        if c and (c.get("field_id") or c.get("fieldId")) and c.get("comparison")
    ]
    if not valid:
        return False
    results = [evaluate_condition(answers, c, sources) for c in valid]
    return any(results) if operator == "OR" else all(results)


def is_hidden_by_logic(
    field: Any, answers: Dict[str, Any], sources: Optional[Dict[str, Any]] = None
) -> bool:
    logic = field.properties.logic if field.properties else None
    if logic is None or not logic.action or not logic.conditions:
        return False
    met = evaluate_conditions(logic.operator, logic.conditions, answers, sources)
    return not met if logic.action == "SHOW" else met


def _title(field: Any) -> str:
    if isinstance(field.title, str) and field.title.strip():
        return field.title.strip()
    return "a question"


def has_answer_value(answer: Any) -> bool:
    """Does an answer carry a value? ``{}`` or ``{"type": "text"}`` does not.
    Twin of the webapp's ``hasAnswerValue``."""
    answer = _as_dict(answer)
    if not isinstance(answer, dict):
        return False

    def filled(value: Any) -> bool:
        if isinstance(value, dict):
            return any(filled(v) for v in value.values())
        return not _is_empty(value)

    return any(filled(v) for k, v in answer.items() if k not in ("field", "type"))


def validate_group_answers(form: StandardForm, answers: Any) -> List[str]:
    """Return human-readable problems with the submitted group answers."""
    if not isinstance(answers, dict):
        return []
    answers = {k: _as_dict(v) for k, v in answers.items()}
    problems: List[str] = []
    sources = logic_sources(form.fields)
    groups = {group.id: group for group in iter_repeating_groups(form)}
    # ``items`` belongs to repeating groups only (not to other questions,
    # nor to imported non-repeating groups).
    for key, raw in answers.items():
        if key not in groups and isinstance(raw, dict) and raw.get("items") is not None:
            problems.append("Only repeating groups can have items.")
            break
    for group in groups.values():
        if group.id not in answers:
            continue
        repeat = group.properties.repeat
        label = repeat.item_label or "item"
        raw = answers.get(group.id)
        # Structure first, for every group answer present — hidden or not:
        # the respondent controls the answers that decide visibility.
        try:
            # Items are typed like top-level answers, and bounded.
            StandardFormResponseAnswer.model_validate(raw)
        except ValidationError:
            problems.append(f"The answer to '{_title(group)}' is malformed.")
            continue
        items = group_items(raw)
        if len(items) > repeat.effective_max:
            problems.append(
                f"'{_title(group)}' allows at most {repeat.effective_max} {label}(s)."
            )
            continue
        children = (group.properties.fields or []) if group.properties else []
        child_ids = {c.id for c in children}
        structural = []
        for position, item in enumerate(items, start=1):
            if set(item) - child_ids:
                structural.append(
                    f"{label} {position} of '{_title(group)}' answers unknown questions."
                )
            elif any(
                isinstance(a, dict) and a.get("items") is not None
                for a in item.values()
            ):
                structural.append("Repeating groups cannot contain another group.")
        if structural:
            problems.extend(structural)
            continue
        # A group hidden by its own rule is dropped before saving
        # (``drop_hidden_group_answers``): no minimum, nothing required.
        if is_hidden_by_logic(group, answers, sources):
            continue
        if len(items) < repeat.effective_min:
            problems.append(
                f"'{_title(group)}' needs at least {repeat.effective_min} {label}(s)."
            )
        for position, item in enumerate(items, start=1):
            scope = {**answers, **item}
            for child in children:
                required = bool(child.validations and child.validations.required)
                if not required or is_hidden_by_logic(child, scope, sources):
                    continue
                if not has_answer_value(item.get(child.id)):
                    problems.append(
                        f"{label} {position}: '{_title(child)}' is required."
                    )
    return problems


def drop_hidden_group_answers(form: StandardForm, answers: Any) -> Any:
    """Remove the answers of repeating groups hidden by their own visibility
    rule, so nothing a hidden group submits is stored. Returns the answers
    (a new dict when something was dropped)."""
    if not isinstance(answers, dict):
        return answers
    plain = {k: _as_dict(v) for k, v in answers.items()}
    sources = logic_sources(form.fields)
    hidden = {
        group.id
        for group in iter_repeating_groups(form)
        if group.id in answers and is_hidden_by_logic(group, plain, sources)
    }
    if not hidden:
        return answers
    return {k: v for k, v in answers.items() if k not in hidden}
