"""Internal ("for office use only") fields.

A field marked ``internal`` is part of the form's definition but belongs to the
organisation, not the respondent: workspace members fill it in on each
submission afterwards (reference number, reviewer, status, ...).

The rules, enforced here and by the services that call these helpers:

- Respondents never see internal fields: every payload that serves a form to
  someone who is not a workspace member goes through ``strip_internal_fields``
  (a page left with nothing but internal fields is dropped as a whole).
- Respondents never see internal values: ``strip_internal_answers`` removes
  them from every respondent-facing response payload.
- A respondent submission may not carry internal answers
  (``reject_respondent_internal_answers`` -> 400).
- Respondent-facing conditional logic (field visibility and page jumps) may not
  depend on an internal field — respondents never answer one
  (``internal_logic_violations``).
- ``validations.required`` on an internal field is stored but not enforced:
  there is no staff-side "complete" state for a submission yet, and respondents
  are never asked for internal fields, so nothing can be required of them.

Forms reach these helpers as pydantic models (snake_case or camelCase DTOs) or
as raw aggregation dicts, so every accessor works on both.
"""

from http import HTTPStatus
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

from backend.app.exceptions import HTTPException

SLIDE_TYPE = "slide"
_INTERNAL_ANSWER_KEYS = (
    "internal_answers",
    "internal_answers_meta",
    "internalAnswers",
    "internalAnswersMeta",
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _set(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)


def _type_value(field: Any) -> Optional[str]:
    field_type = _get(field, "type")
    return getattr(field_type, "value", field_type)


def is_internal(field: Any) -> bool:
    return bool(_get(field, "internal"))


def iter_question_fields(form: Any) -> Iterator[Any]:
    """Every question of a form: the fields inside v2 slides, or the top-level
    fields of a flat (v1/imported) form."""
    for field in _get(form, "fields") or []:
        if _type_value(field) == SLIDE_TYPE:
            yield from _get(_get(field, "properties"), "fields") or []
        else:
            yield field


def internal_fields(form: Any) -> List[Any]:
    return [field for field in iter_question_fields(form) if is_internal(field)]


def internal_field_ids(form: Any) -> Set[str]:
    return {
        str(_get(field, "id")) for field in internal_fields(form) if _get(field, "id")
    }


def strip_internal_fields(form: Any) -> Any:
    """Remove internal fields from a form payload in place (and return it).

    A page whose fields were all internal is removed too — otherwise the
    respondent would face an empty page. Pages that were empty to begin with
    are kept as they are."""
    if form is None:
        return form
    fields = _get(form, "fields")
    if not fields:
        return form
    kept_top: List[Any] = []
    for field in fields:
        if is_internal(field):
            continue
        properties = _get(field, "properties")
        children = _get(properties, "fields") if properties is not None else None
        if _type_value(field) == SLIDE_TYPE and children:
            kept_children = [child for child in children if not is_internal(child)]
            if len(kept_children) != len(children):
                if not kept_children:
                    continue
                _set(properties, "fields", kept_children)
        kept_top.append(field)
    _set(form, "fields", kept_top)
    return form


def strip_internal_answers(response: Any) -> Any:
    """Remove staff-entered values from a response payload in place."""
    if response is None:
        return response
    if isinstance(response, dict):
        for key in _INTERNAL_ANSWER_KEYS:
            response.pop(key, None)
    else:
        for key in _INTERNAL_ANSWER_KEYS[:2]:
            if hasattr(response, key):
                setattr(response, key, None)
    return response


def _condition_source(condition: Any) -> Optional[str]:
    return _get(condition, "field_id") or _get(condition, "fieldId")


def internal_logic_violations(form: Any) -> List[str]:
    """Human-readable reasons respondent logic depends on an internal field."""
    internal_ids = internal_field_ids(form)
    if not internal_ids:
        return []
    problems: List[str] = []

    def _check(conditions: Iterable[Any], where: str) -> None:
        for condition in conditions or []:
            source = _condition_source(condition)
            if source and str(source) in internal_ids:
                problems.append(
                    f"{where} depends on internal field '{source}' — respondents "
                    "never answer internal fields, so logic cannot use them."
                )

    for field in _get(form, "fields") or []:
        properties = _get(field, "properties")
        for jump in _get(properties, "jumps") or []:
            _check(
                _get(jump, "conditions"), f"A page jump on page '{_get(field, 'id')}'"
            )
    for field in iter_question_fields(form):
        logic = _get(_get(field, "properties"), "logic")
        _check(
            _get(logic, "conditions"), f"The visibility rule of '{_get(field, 'id')}'"
        )
    return problems


def ensure_no_internal_logic(form: Any) -> None:
    problems = internal_logic_violations(form)
    if problems:
        raise HTTPException(HTTPStatus.BAD_REQUEST, content=problems[0])


def reject_respondent_internal_answers(response: Any, internal_ids: Set[str]) -> None:
    """A respondent submission (or a respondent's edit of one) may not carry
    internal values — neither in the dedicated slot nor disguised as a regular
    answer keyed by an internal field's id."""
    if _get(response, "internal_answers") or _get(response, "internal_answers_meta"):
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            content="Internal answers cannot be submitted by respondents.",
        )
    answers = _get(response, "answers")
    if isinstance(answers, dict) and internal_ids.intersection(answers.keys()):
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            content="The submission contains answers for internal fields.",
        )


def fields_by_id(fields: Iterable[Any]) -> Dict[str, Any]:
    return {str(_get(field, "id")): field for field in fields if _get(field, "id")}
