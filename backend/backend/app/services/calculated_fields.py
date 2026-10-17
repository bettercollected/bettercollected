"""Calculated fields: values computed from a respondent's answers.

A ``calculated`` field on a page stores an expressions-v1 AST at
``properties.expression`` (docs/spec/expressions-v1.md), a display format at
``properties.format`` and, optionally, ``properties.hidden_from_respondents``
(computed and stored, never shown). The webapp twin is
``webapp/src/utils/calculated-fields.ts``; keep the two in step.

- **Variables** (one namespace with conditional logic and answer piping): a
  page question's id reads its answer as logic reads it
  (``comparable_answer_value``); ``<group id>.<question id>`` reads a
  repeating group's question across its items as a list; a declared hidden
  field's name reads its captured URL parameter; another calculated field's id
  reads its computed value. Field ids win over hidden-field names. Internal
  (staff-only) fields, content blocks and matrices are not variables.
- **Saving** (``calculated_field_problems``): the AST must be well formed, use
  only known variables, never an internal field, and calculated fields must
  not depend on each other in a circle. Problems carry the field id and the
  JSON pointer of the node inside the expression.
- **Submitting** (``apply_calculated_fields``): the server recomputes every
  calculated field from the submitted answers, in dependency order, and
  stores its own values; whatever a client sent for these fields is dropped.
  Logic, page jumps and Required checks that use calculated fields then read
  the server's values. Inputs are capped by the evaluator (texts over 10,000
  characters and lists over 1,000 items count as empty).
- **Unanswered as 0** (``properties.unanswered_as_zero``, default on unless
  the format is text): a question or calculation the formula reads that has
  no value (null or "") reads as 0, so one empty optional number doesn't
  blank a total. Group lists and hidden fields are read as they are. Shared
  cases with the webapp: ``docs/spec/calculated-fields.cases.json``.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

from common.expressions import (
    ExpressionError,
    evaluate_expression,
    format_expression_value,
    validate_expression,
)
from common.models.standard_form import _find_cycle, is_iso_date

from backend.app.exceptions import HTTPException
from backend.app.services.repeating_groups import (
    comparable_answer_value,
    group_items,
)

CALCULATED = "calculated"
# Most calculated fields one form may have (every save path refuses more).
MAX_CALCULATED_FIELDS = 50
SLIDE = "slide"
GROUP = "group"
MATRIX = "matrix"
ERROR_CODE = "invalid_calculation"
# Field types that hold no answer a formula could read.
NOT_VARIABLES = {
    SLIDE,
    MATRIX,
    "text",
    "statement",
    "page_break",
    "hidden",
    "conditional",
    "payment",
    "tabular_input",
    "file_upload",
    "VIDEO_CONTENT",
    "IMAGE_CONTENT",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "p",
    "strong",
    "divider",
    "markdown",
}


@dataclass(frozen=True)
class CalculationProblem:
    """A problem with one calculated field: its id, the JSON pointer of the
    expression node (``""`` = the whole expression) and a readable message."""

    field_id: str
    path: str
    message: str

    def as_json(self) -> Dict[str, str]:
        return {"fieldId": self.field_id, "path": self.path, "message": self.message}


def _get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _type(field: Any) -> Optional[str]:
    value = _get(field, "type")
    return getattr(value, "value", value)


def _children(field: Any) -> List[Any]:
    return list(_get(_get(field, "properties"), "fields") or [])


def _is_repeating_group(field: Any) -> bool:
    return (
        _type(field) == GROUP and _get(_get(field, "properties"), "repeat") is not None
    )


def _title(field: Any) -> str:
    title = _get(field, "title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    if isinstance(title, dict):
        text = _plain_text(title).strip()
        if text:
            return text
    return str(_get(field, "id") or "a calculation")


def _plain_text(node: Any) -> str:
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            return node["text"]
        return "".join(_plain_text(child) for child in node.get("content") or [])
    return ""


def page_fields(form: Any) -> List[Any]:
    """The fields on the pages of a page-based form (none for other forms)."""
    fields = list(_get(form, "fields") or [])
    if not fields or any(_type(field) != SLIDE for field in fields):
        return []
    return [field for slide in fields for field in _children(slide)]


def calculated_fields(form: Any) -> List[Any]:
    return [field for field in page_fields(form) if _type(field) == CALCULATED]


def is_calculated(field: Any) -> bool:
    return _type(field) == CALCULATED


def _expression(field: Any) -> Any:
    return _get(_get(field, "properties"), "expression")


def variable_keys(form: Any) -> Set[str]:
    """Every key a formula of this form may read."""
    keys: Set[str] = set(str(name) for name in (_get(form, "hidden_fields") or []))
    for field in page_fields(form):
        field_id = _get(field, "id")
        if not field_id or _get(field, "internal"):
            continue
        if _is_repeating_group(field):
            for child in _children(field):
                child_id = _get(child, "id")
                if child_id and not _get(child, "internal"):
                    keys.add(f"{field_id}.{child_id}")
            continue
        if _type(field) in NOT_VARIABLES or _type(field) == GROUP:
            continue
        keys.add(str(field_id))
    return keys


def expression_variables(ast: Any) -> List[str]:
    """The variable keys a well-formed AST reads, in order of appearance."""
    found: List[str] = []
    pending = [ast]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict) or len(node) != 1:
            continue
        op, value = next(iter(node.items()))
        if op == "var":
            if isinstance(value, str) and value not in found:
                found.append(value)
        elif isinstance(value, list):
            pending.extend(reversed(value))
    return found


def _misplaced_calculations(form: Any) -> List[Any]:
    """Calculated fields of a page-based form that are not directly on a
    page (inside a group, or at the top next to the pages). Only page-level
    calculations are computed. Forms without any page (imports) keep
    whatever their provider gave them: nothing there is computed."""
    top = list(_get(form, "fields") or [])
    if not any(_type(field) == SLIDE for field in top):
        return []
    on_pages = {
        id(field)
        for slide in top
        if _type(slide) == SLIDE
        for field in _children(slide)
    }
    misplaced: List[Any] = []
    pending = list(_get(form, "fields") or [])
    while pending:
        field = pending.pop()
        if is_calculated(field) and id(field) not in on_pages:
            misplaced.append(field)
        pending.extend(_children(field))
    return misplaced


def calculated_field_problems(form: Any) -> List[CalculationProblem]:
    """Problems with the calculated fields of a form (see the module doc)."""
    problems: List[CalculationProblem] = [
        CalculationProblem(
            str(_get(field, "id") or ""),
            "",
            f"'{_title(field)}' must be on a page: calculations cannot be placed "
            "inside a group or in a form without pages.",
        )
        for field in _misplaced_calculations(form)
    ]
    calcs = calculated_fields(form)
    if not calcs:
        return problems
    if len(calcs) > MAX_CALCULATED_FIELDS:
        problems.append(
            CalculationProblem(
                "",
                "",
                f"A form can have at most {MAX_CALCULATED_FIELDS} calculated fields; "
                f"this one has {len(calcs)}.",
            )
        )
    known = variable_keys(form)
    internal_ids = {
        str(_get(field, "id"))
        for field in page_fields(form)
        if _get(field, "internal") and _get(field, "id")
    }
    calc_ids = {str(_get(field, "id")) for field in calcs if _get(field, "id")}
    by_id = {str(_get(field, "id")): field for field in calcs}
    edges: Dict[str, List[str]] = {}
    for field in calcs:
        field_id = str(_get(field, "id") or "")
        if _get(_get(field, "validations"), "required"):
            problems.append(
                CalculationProblem(
                    field_id,
                    "",
                    f"'{_title(field)}' is a calculation: it is computed, never "
                    "answered, so it cannot be required.",
                )
            )
        if _get(field, "internal"):
            problems.append(
                CalculationProblem(
                    field_id,
                    "",
                    f"The calculation '{_title(field)}' cannot be an internal field: "
                    "it is computed from the respondent's answers.",
                )
            )
            continue
        ast = _expression(field)
        if ast is None:
            continue
        structural = validate_expression(ast)
        if structural:
            problems.extend(
                CalculationProblem(field_id, p.path, f"'{_title(field)}': {p.message}")
                for p in structural
            )
            continue
        for problem in validate_expression(ast, known):
            key = _var_at(ast, problem.path)
            if key in internal_ids:
                message = (
                    f"'{_title(field)}' uses an internal field — respondents never "
                    "answer internal fields, so a calculation cannot use them."
                )
            else:
                message = f"'{_title(field)}' uses an unknown field or hidden field."
            problems.append(CalculationProblem(field_id, problem.path, message))
        refs = [key for key in expression_variables(ast) if key in calc_ids]
        if refs:
            edges[field_id] = refs
    cycle = _find_cycle(edges)
    if cycle:
        names = [_title(by_id[key]) for key in cycle if key in by_id]
        problems.append(
            CalculationProblem(
                cycle[0],
                "",
                "Calculations cannot depend on each other in a circle ("
                + " → ".join(f"'{name}'" for name in names + names[:1])
                + ").",
            )
        )
    return problems


def _var_at(ast: Any, pointer: str) -> Optional[str]:
    """The variable key at a validator path (``/+/1/var``)."""
    node = ast
    parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.split("/")[1:]]
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return node if isinstance(node, str) else None


def ensure_valid_calculations(form: Any) -> None:
    """422 with every problem (field id, path in the expression, message)."""
    problems = calculated_field_problems(form)
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": " ".join(p.message for p in problems),
                "errors": [p.as_json() for p in problems],
            },
        )


def evaluation_order(calcs: Iterable[Any]) -> List[Any]:
    """Calculated fields ordered so that every field comes after the ones it
    reads. Fields in a circle (only in stored data from before the check)
    come last and evaluate to nothing."""
    calcs = list(calcs)
    by_id = {str(_get(field, "id")): field for field in calcs}
    deps = {
        key: [ref for ref in expression_variables(_expression(field)) if ref in by_id]
        for key, field in by_id.items()
    }
    ordered: List[Any] = []
    done: Set[str] = set()
    progress = True
    while progress:
        progress = False
        for key, field in by_id.items():
            if key in done or any(ref not in done for ref in deps[key]):
                continue
            done.add(key)
            ordered.append(field)
            progress = True
    return ordered


def _plain(answers: Any) -> Dict[str, Any]:
    if not isinstance(answers, dict):
        return {}
    return {
        str(key): (
            value.model_dump(exclude_none=True)
            if hasattr(value, "model_dump")
            else value
        )
        for key, value in answers.items()
    }


def build_variables(
    form: Any, answers: Mapping[str, Any], hidden_values: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    """The variables map of the answer-based keys (calculated values are
    added while evaluating)."""
    variables: Dict[str, Any] = {}
    declared = {str(name) for name in (_get(form, "hidden_fields") or [])}
    for name, value in (hidden_values or {}).items():
        if name in declared and isinstance(value, str):
            variables[name] = value
    for field in page_fields(form):
        field_id = _get(field, "id")
        if not field_id or _get(field, "internal") or is_calculated(field):
            continue
        if _is_repeating_group(field):
            items = group_items(answers.get(str(field_id)))
            for child in _children(field):
                child_id = _get(child, "id")
                if not child_id or _get(child, "internal"):
                    continue
                variables[f"{field_id}.{child_id}"] = [
                    comparable_answer_value(item.get(str(child_id)), _type(child))
                    for item in items
                ]
            continue
        if _type(field) in NOT_VARIABLES or _type(field) == GROUP:
            continue
        variables[str(field_id)] = comparable_answer_value(
            answers.get(str(field_id)), _type(field)
        )
    return variables


def unanswered_as_zero(field: Any) -> bool:
    """Do unanswered questions this calculation reads count as 0? Its own
    setting, else on unless it shows text."""
    properties = _get(field, "properties")
    setting = _get(properties, "unanswered_as_zero")
    if setting is not None:
        return bool(setting)
    style = _get(_get(properties, "format"), "style")
    return style != "text"


def _question_keys(form: Any) -> Set[str]:
    """Keys that read one question's answer or one calculation: the ones
    "unanswered as 0" applies to (never group lists or hidden fields)."""
    keys: Set[str] = set()
    for field in page_fields(form):
        field_id = _get(field, "id")
        if not field_id or _get(field, "internal"):
            continue
        if _type(field) in NOT_VARIABLES or _type(field) == GROUP:
            continue
        keys.add(str(field_id))
    return keys


def compute_calculated_values(
    form: Any,
    answers: Any,
    hidden_values: Optional[Mapping[str, Any]] = None,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Every calculated field's value (None when it has none), computed from
    ``answers`` in dependency order with the Python evaluator."""
    calcs = [
        field
        for field in calculated_fields(form)
        if _get(field, "id") and not _get(field, "internal")
    ]
    if not calcs:
        return {}
    plain = _plain(answers)
    variables = build_variables(form, plain, hidden_values)
    context = {"today": today} if today else {}
    values: Dict[str, Any] = {str(_get(field, "id")): None for field in calcs}
    question_keys = _question_keys(form)
    for field in evaluation_order(calcs):
        field_id = str(_get(field, "id"))
        ast = _expression(field)
        value = None
        if ast is not None:
            reading = variables
            if unanswered_as_zero(field):
                reading = dict(variables)
                for key in expression_variables(ast):
                    if key in question_keys and reading.get(key) in (None, ""):
                        reading[key] = 0
            try:
                value = evaluate_expression(ast, reading, context)
            except (ExpressionError, RecursionError):
                value = None
        variables[field_id] = value
        values[field_id] = value
    return values


def calculated_answer(field_id: str, value: Any) -> Dict[str, Any]:
    """The stored answer of a calculated field: a number, a yes/no (boolean)
    or a text; an empty answer (no value slot) when there is no value."""
    answer: Dict[str, Any] = {"field": {"id": field_id}}
    if isinstance(value, bool):
        answer.update(type="boolean", boolean=value)
    elif isinstance(value, Decimal):
        number: Any = int(value) if value == value.to_integral_value() else float(value)
        answer.update(type="number", number=number)
    elif isinstance(value, str) and value != "":
        answer.update(type="text", text=value)
    elif isinstance(value, list):
        text = format_expression_value(value)
        answer.update(type="text", **({"text": text} if text else {}))
    else:
        answer["type"] = "text"
    return answer


def has_calculated_value(answer: Dict[str, Any]) -> bool:
    return any(answer.get(slot) is not None for slot in ("number", "boolean", "text"))


def today_iso(day: Optional[dt.date] = None) -> str:
    return (day or dt.datetime.now(dt.timezone.utc).date()).isoformat()


def apply_calculated_fields(
    form: Any,
    answers: Any,
    hidden_values: Optional[Mapping[str, Any]] = None,
    today: Optional[str] = None,
    keep_empty: bool = False,
) -> Any:
    """``answers`` with every calculated field's answer replaced by the
    server's value: what a client sent for them is dropped, a value is
    stored, and nothing is stored for an empty result (``keep_empty``: an
    empty answer instead, so that an edit overwrites a stored value)."""
    calcs = calculated_fields(form)
    if not calcs:
        return answers
    # no answers at all still gives every calculation its value (a sum of
    # nothing is 0), so logic on it is enforced
    out = dict(answers) if isinstance(answers, dict) else {}
    for field in calcs:
        out.pop(str(_get(field, "id")), None)
    for field_id, value in compute_calculated_values(
        form, out, hidden_values, today
    ).items():
        answer = calculated_answer(field_id, value)
        if has_calculated_value(answer) or keep_empty:
            out[field_id] = answer
    return out


def hidden_calculation_ids(form: Any) -> Set[str]:
    """Ids of the calculations a form keeps from respondents."""
    return {
        str(_get(field, "id"))
        for field in calculated_fields(form)
        if _get(field, "id")
        and _get(_get(field, "properties"), "hidden_from_respondents")
    }


def drop_answers(response: Any, ids: Set[str]) -> Any:
    """Remove the answers to ``ids`` from a (decrypted) response in place:
    a respondent's copy never carries a calculation kept from them."""
    answers = _get(response, "answers")
    if ids and isinstance(answers, dict):
        for key in ids:
            answers.pop(key, None)
    return response


def respondent_today(client_today: Any) -> str:
    """The "today" a submission is computed with: the respondent's own date
    (their browser computed with it) when it is a ``YYYY-MM-DD`` date within
    a day of the UTC date (``date_rules.today_range``), else the server's."""
    from backend.app.services.date_rules import today_range

    if isinstance(client_today, str) and is_iso_date(client_today):
        low, high = today_range()
        if low <= client_today <= high:
            return client_today
    return today_iso()


def drop_draft_calculations(answers: Any, draft: Any, published: Any) -> Any:
    """Answers without values of calculated fields that exist only in the
    draft (not in the version respondents fill): nothing computes them."""
    if not isinstance(answers, dict) or draft is None or published is None:
        return answers
    published_ids = {str(_get(field, "id")) for field in calculated_fields(published)}
    draft_only = {
        str(_get(field, "id"))
        for field in calculated_fields(draft)
        if str(_get(field, "id")) not in published_ids
    }
    if not draft_only:
        return answers
    return {key: value for key, value in answers.items() if key not in draft_only}


def calculate_and_check(
    form: Any,
    answers: Any,
    form_id: str,
    hidden_values: Optional[Mapping[str, Any]] = None,
    today: Optional[str] = None,
    keep_empty: bool = False,
    known_ids: Optional[Set[str]] = None,
    only: Optional[Iterable[str]] = None,
) -> Any:
    """The server's calculated values, then answer validation with them
    (Required, rules, types, logic and jumps): one call, run off the event
    loop by the caller. Returns the answers with the calculated values."""
    from backend.app.services.answer_validation import check_answers

    answers = apply_calculated_fields(
        form, answers, hidden_values, today=today, keep_empty=keep_empty
    )
    check_answers(form, answers, form_id, known_ids=known_ids, only=only)
    return answers
