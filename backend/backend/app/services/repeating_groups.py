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
a missing group answer is therefore accepted (the server does not re-run
page navigation), but a submitted one must respect the limits.
"""

from typing import Any, Dict, Iterable, List, Optional

from common.models.standard_form import StandardForm, StandardFormFieldType
from pydantic import BaseModel

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


def evaluate_condition(answers: Dict[str, Any], condition: Any) -> bool:
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
        matches = [evaluate_condition({**answers, **item}, child) for item in items]
        if group_mode == "ANY":
            return any(matches)
        if group_mode == "ALL":
            return bool(matches) and all(matches)
        return False
    value = comparable_answer_value(
        answers.get(field_id), get("field_type", "fieldType")
    )
    return compare(value, comparison, target)


def evaluate_conditions(
    operator: Optional[str], conditions: Any, answers: Dict[str, Any]
) -> bool:
    valid = [
        c
        for c in (_as_dict(c) for c in (conditions or []))
        if c and (c.get("field_id") or c.get("fieldId")) and c.get("comparison")
    ]
    if not valid:
        return False
    results = [evaluate_condition(answers, c) for c in valid]
    return any(results) if operator == "OR" else all(results)


def is_hidden_by_logic(field: Any, answers: Dict[str, Any]) -> bool:
    logic = field.properties.logic if field.properties else None
    if logic is None or not logic.action or not logic.conditions:
        return False
    met = evaluate_conditions(logic.operator, logic.conditions, answers)
    return not met if logic.action == "SHOW" else met


def _title(field: Any) -> str:
    if isinstance(field.title, str) and field.title.strip():
        return field.title.strip()
    return "a question"


def validate_group_answers(form: StandardForm, answers: Any) -> List[str]:
    """Return human-readable problems with the submitted group answers."""
    if not isinstance(answers, dict):
        return []
    answers = {k: _as_dict(v) for k, v in answers.items()}
    problems: List[str] = []
    for group in iter_repeating_groups(form):
        if group.id not in answers:
            continue
        repeat = group.properties.repeat
        label = repeat.item_label or "item"
        raw = answers.get(group.id)
        if not isinstance(raw, dict) or (
            raw.get("items") is not None and not isinstance(raw.get("items"), list)
        ):
            problems.append(f"The answer to '{_title(group)}' is malformed.")
            continue
        items = group_items(raw)
        if len(items) < repeat.effective_min:
            problems.append(
                f"'{_title(group)}' needs at least {repeat.effective_min} {label}(s)."
            )
        if len(items) > repeat.effective_max:
            problems.append(
                f"'{_title(group)}' allows at most {repeat.effective_max} {label}(s)."
            )
            continue
        children = (group.properties.fields or []) if group.properties else []
        child_ids = {c.id for c in children}
        for position, item in enumerate(items, start=1):
            unknown = set(item) - child_ids
            if unknown:
                problems.append(
                    f"{label} {position} of '{_title(group)}' answers unknown questions."
                )
                continue
            scope = {**answers, **item}
            for child in children:
                required = bool(child.validations and child.validations.required)
                if not required or is_hidden_by_logic(child, scope):
                    continue
                # Same rule as the webapp's validateSlide: a required
                # question needs an answer object (cleared inputs remove it).
                if not item.get(child.id):
                    problems.append(
                        f"{label} {position}: '{_title(child)}' is required."
                    )
    return problems
