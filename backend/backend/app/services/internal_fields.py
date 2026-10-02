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
- A respondent submission never stores internal answers: any it carries are
  dropped (``drop_respondent_internal_answers``), not rejected — a field made
  internal while someone was filling the form must not fail their submission.
- Respondent-facing conditional logic (field visibility and page jumps) may not
  depend on an internal field — respondents never answer one
  (``internal_logic_violations``).
- ``validations.required`` on an internal field is stored but not enforced:
  there is no staff-side "complete" state for a submission yet, and respondents
  are never asked for internal fields, so nothing can be required of them.

Forms reach these helpers as pydantic models (snake_case or camelCase DTOs) or
as raw aggregation dicts, so every accessor works on both.
"""

import datetime as dt
import json
import re
from http import HTTPStatus
from urllib.parse import urlparse
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

from loguru import logger

from backend.app.exceptions import HTTPException

SLIDE_TYPE = "slide"
GROUP_TYPE = "group"
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


def _group_children(field: Any) -> List[Any]:
    if _type_value(field) != GROUP_TYPE:
        return []
    return _get(_get(field, "properties"), "fields") or []


def iter_question_fields(form: Any) -> Iterator[Any]:
    """Every question of a form: the fields inside v2 slides, or the top-level
    fields of a flat (v1/imported) form — and the questions inside groups.

    Internal fields are not allowed inside repeating groups (the model rejects
    them); walking group children anyway means strip/drop would still cover
    one if it ever got there."""
    for field in _get(form, "fields") or []:
        questions = (
            _get(_get(field, "properties"), "fields") or []
            if _type_value(field) == SLIDE_TYPE
            else [field]
        )
        for question in questions:
            yield question
            yield from _group_children(question)


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
    # who allowed AI insights is staff information: respondents only need to
    # know that (and to which provider) responses may be analysed
    settings = _get(form, "settings")
    if settings is not None and _get(settings, "ai_insights_enabled_by") is not None:
        _set(settings, "ai_insights_enabled_by", None)
    fields = _get(form, "fields")
    if not fields:
        return form

    def _strip_group_children(question: Any) -> None:
        children = _group_children(question)
        if children and any(is_internal(child) for child in children):
            _set(
                _get(question, "properties"),
                "fields",
                [child for child in children if not is_internal(child)],
            )

    kept_top: List[Any] = []
    for field in fields:
        if is_internal(field):
            continue
        _strip_group_children(field)
        properties = _get(field, "properties")
        children = _get(properties, "fields") if properties is not None else None
        if _type_value(field) == SLIDE_TYPE and children:
            for child in children:
                _strip_group_children(child)
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


def drop_respondent_internal_answers(response: Any, internal_ids: Set[str]) -> int:
    """Remove internal values from a respondent submission (or a respondent's
    edit of one) before it is stored: the dedicated staff slot, and answers
    keyed by an internal field's id. Returns how many were dropped.

    Dropped rather than rejected: a respondent who loaded the form before a
    field was marked internal still answers it, and their submission must go
    through. Only the count is logged — never the values."""
    dropped = 0
    for key in ("internal_answers", "internal_answers_meta"):
        value = _get(response, key)
        if value:
            dropped += len(value) if isinstance(value, dict) else 1
            _set(response, key, None)
    answers = _get(response, "answers")
    if isinstance(answers, dict):
        for field_id in internal_ids.intersection(answers.keys()):
            answers.pop(field_id, None)
            dropped += 1
        # ...and inside repeating-group items (keyed by child field id).
        for answer in answers.values():
            items = _get(answer, "items")
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict):
                    for field_id in internal_ids.intersection(item.keys()):
                        item.pop(field_id, None)
                        dropped += 1
    if dropped:
        logger.info(
            f"Dropped {dropped} internal answer(s) from a respondent submission."
        )
    return dropped


# One internal answer is a short staff note, never a document: cap its size so
# the endpoint can't be used to park arbitrary payloads on a response.
MAX_INTERNAL_ANSWER_BYTES = 10_000

# Field type -> (the answer slot it fills, its response type). The types staff
# can fill in from the dashboard; choice fields are handled separately.
_INTERNAL_VALUE_SLOTS = {
    "short_text": ("text", "text"),
    "long_text": ("text", "text"),
    "number": ("number", "number"),
    "date": ("date", "date"),
    "email": ("email", "email"),
    "url": ("url", "url"),
    "phone_number": ("phone_number", "phone_number"),
    "yes_no": ("boolean", "boolean"),
}
CHOICE_FIELD_TYPES = ("multiple_choice", "dropdown")
INTERNAL_CAPABLE_TYPES = frozenset(_INTERNAL_VALUE_SLOTS) | frozenset(
    CHOICE_FIELD_TYPES
)
_ANSWER_SLOTS = {
    "text",
    "choice",
    "choices",
    "number",
    "boolean",
    "email",
    "date",
    "url",
    "file_url",
    "payment",
    "phone_number",
    "file_metadata",
    "tabular_value",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _unprocessable(field_id: str, reason: str) -> HTTPException:
    return HTTPException(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        content=f"Invalid answer for internal field '{field_id}': {reason}",
    )


def validate_internal_answer(field: Any, value: Dict[str, Any]) -> Dict[str, Any]:
    """Check a staff answer against its field's type and options; return the
    stored shape (``field`` + ``type`` + exactly one value slot). 422 on any
    mismatch: a value in another type's slot, a choice that is not an option,
    a malformed date/email/url, or a field type that can't be filled here."""
    from common.models.standard_form import StandardFormResponseAnswer

    field_id = str(_get(field, "id"))
    field_type = _type_value(field)
    if not isinstance(value, dict):
        raise _unprocessable(field_id, "an answer object is expected.")
    try:
        answer = StandardFormResponseAnswer.model_validate(value)
    except ValueError:
        raise _unprocessable(field_id, "the answer is malformed.")
    given = {
        slot
        for slot in _ANSWER_SLOTS
        if getattr(answer, slot, None) not in (None, "", [])
    }

    if field_type in CHOICE_FIELD_TYPES:
        properties = _get(field, "properties")
        options = {str(_get(c, "id")) for c in _get(properties, "choices") or []}
        multiple = bool(_get(properties, "allow_multiple_selection"))
        slot, response_type = (
            ("choices", "choices") if multiple else ("choice", "choice")
        )
        if given != {slot}:
            raise _unprocessable(
                field_id, f"a '{slot}' value is expected for this field."
            )
        if multiple:
            picked = answer.choices.values or []
            if answer.choices.other or not picked:
                raise _unprocessable(field_id, "pick at least one of its options.")
            if not set(picked) <= options:
                raise _unprocessable(field_id, "a value is not one of its options.")
            clean = {"choices": {"values": list(dict.fromkeys(picked))}}
        else:
            if answer.choice.other or answer.choice.value not in options:
                raise _unprocessable(field_id, "the value is not one of its options.")
            clean = {"choice": {"value": answer.choice.value}}
    elif field_type in _INTERNAL_VALUE_SLOTS:
        slot, response_type = _INTERNAL_VALUE_SLOTS[field_type]
        if given != {slot}:
            raise _unprocessable(
                field_id, f"a '{slot}' value is expected for this field."
            )
        raw = getattr(answer, slot)
        if slot in ("text", "email", "url", "phone_number", "date") and not isinstance(
            raw, str
        ):
            raise _unprocessable(field_id, f"'{slot}' must be text.")
        if slot == "date":
            try:
                dt.date.fromisoformat(raw[:10])
            except ValueError:
                raise _unprocessable(field_id, "the date must be YYYY-MM-DD.")
        if slot == "email" and not _EMAIL.match(raw):
            raise _unprocessable(field_id, "not an email address.")
        if slot == "url" and urlparse(raw).scheme not in ("http", "https"):
            raise _unprocessable(field_id, "the link must start with http(s)://.")
        clean = {slot: raw}
    else:
        raise _unprocessable(
            field_id, f"'{field_type}' fields can't be filled in by staff."
        )

    if answer.type is not None and answer.type.value != response_type:
        raise _unprocessable(field_id, f"the type must be '{response_type}'.")
    stored = {"field": {"id": field_id}, "type": response_type, **clean}
    if len(json.dumps(stored)) > MAX_INTERNAL_ANSWER_BYTES:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            content=f"The answer for internal field '{field_id}' is too long.",
        )
    return stored


def fields_by_id(fields: Iterable[Any]) -> Dict[str, Any]:
    return {str(_get(field, "id")): field for field in fields if _get(field, "id")}
