"""The answers of an API submission, as the respondent path's own answer
objects.

An API caller names answers by question id. A value is either

* the stored typed answer object, the shape ``GET .../responses/{id}`` returns
  (``{"type": "text", "text": "..."}``), so what is read can be written back, or
* a shorthand for the common types (``"Ada"`` for a text question, ``4`` for a
  rating, ``true`` for yes/no, an option id or its text for a choice, a list for
  tags or a multiple selection, an object for a currency, date range or address,
  a list of objects for a repeating group).

Everything is turned into typed answer objects here and nothing else is decided
here: the respondent path's validation (``answer_validation``, field rules,
choice logic, calculated fields, required, patterns, date rules) judges them
afterwards, exactly as it judges a respondent's. This module only refuses what
the API does not take: questions of a type it does not support (files,
signatures, payments, see ``UNSUPPORTED_TYPES``), answer slots that would carry
a file reference or a signature image, and shapes it cannot read.

Problems are reported per question as ``{"fieldId", "rule"[, "item"]}``, the
respondent path's own error shape (``answer_validation.AnswerProblem``).
"""

from typing import Any, Dict, List, Optional, Tuple

from common.models.standard_form import StandardFormResponseAnswer

from backend.app.services.answer_validation import (
    NUMBER_TYPES,
    TEXT_TYPES,
    TYPE,
    UNKNOWN_FIELD,
    is_repeating_group,
)

# a question of these types takes no answer through the API (files and
# signatures need an upload step, a payment a provider flow): the first
# version refuses them with this code, instead of storing something unchecked
NOT_SUPPORTED = "question_not_supported"
UNSUPPORTED_TYPES = {"file_upload", "signature", "payment"}
# answer slots that would hold a file reference, a stored image or a payment:
# never accepted from a caller, on any question
FORBIDDEN_SLOTS = {"file_url", "file_metadata", "signature", "payment", "field"}
# the most answers one request may carry (a form's own limit is lower)
MAX_ANSWERS = 500

_TYPED_SLOTS = set(StandardFormResponseAnswer.model_fields) - FORBIDDEN_SLOTS

# field type -> (answer slot, the answer's ``type``, python types accepted)
_SIMPLE: Dict[str, Tuple[str, str, tuple]] = {
    "email": ("email", "email", (str,)),
    "url": ("url", "url", (str,)),
    "phone_number": ("phone_number", "phone_number", (str,)),
    "date": ("date", "date", (str,)),
    "day": ("date", "date", (str,)),
    "time": ("time", "time", (str,)),
    "yes_no": ("boolean", "boolean", (bool,)),
    "tags": ("tags", "tags", (list,)),
    "currency": ("currency", "currency", (dict,)),
    "date_range": ("date_range", "date_range", (dict,)),
    "address": ("address", "address", (dict,)),
}


def _kind(field: Any) -> str:
    kind = getattr(field, "type", None)
    return str(getattr(kind, "value", kind))


def _children(field: Any) -> List[Any]:
    return list(getattr(getattr(field, "properties", None), "fields", None) or [])


def question_index(form: Any) -> Dict[str, Any]:
    """Question id -> field, for the questions of a form's pages, as the
    respondent path's check reads them: the questions inside a plain group
    and the rows of a matrix are top-level answers too; those inside a
    repeating group are answered through the group."""
    index: Dict[str, Any] = {}
    for page in getattr(form, "fields", None) or []:
        for field in _children(page):
            if getattr(field, "id", None):
                index[str(field.id)] = field
            if is_repeating_group(field):
                continue
            for child in _children(field):
                if getattr(child, "id", None):
                    index.setdefault(str(child.id), child)
    return index


def _choice_id(field: Any, value: str) -> str:
    """An option named by its id or by its text becomes its id; anything else
    is left as sent, for the choice check to refuse."""
    options = list(getattr(getattr(field, "properties", None), "choices", None) or [])
    for option in options:
        if str(getattr(option, "id", "")) == value:
            return value
    for option in options:
        if getattr(option, "value", None) == value and getattr(option, "id", None):
            return str(option.id)
    return value


def _multiple(field: Any) -> bool:
    return _kind(field) == "multiple_choice" and bool(
        getattr(
            getattr(field, "properties", None), "allow_multiple_selection", None
        )
    )


class _Problems:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def add(self, field_id: str, rule: str, item: Optional[int] = None) -> None:
        problem: Dict[str, Any] = {"fieldId": field_id, "rule": rule}
        if item is not None:
            problem["item"] = item
        self.items.append(problem)


def _typed(value: Dict[str, Any]) -> Optional[str]:
    """A typed answer object: its problem code, or None when it is one we
    take (only the answer slots, none that carries a file or a signature)."""
    if any(key in FORBIDDEN_SLOTS for key in value):
        return NOT_SUPPORTED
    if not set(value) <= _TYPED_SLOTS:
        return TYPE
    return None


def _shorthand(field: Any, value: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(the typed answer, None) or (None, the problem code)."""
    kind = _kind(field)
    if kind in TEXT_TYPES:
        if isinstance(value, str):
            return {"type": "text", "text": value}, None
        return None, TYPE
    if kind in NUMBER_TYPES:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {"type": "number", "number": value}, None
        return None, TYPE
    if kind in ("multiple_choice", "dropdown"):
        if _multiple(field):
            picked = [value] if isinstance(value, str) else value
            if isinstance(picked, list) and all(isinstance(v, str) for v in picked):
                return {
                    "type": "choices",
                    "choices": {"values": [_choice_id(field, v) for v in picked]},
                }, None
            return None, TYPE
        if isinstance(value, str):
            return {
                "type": "choice",
                "choice": {"value": _choice_id(field, value)},
            }, None
        return None, TYPE
    simple = _SIMPLE.get(kind)
    if simple is not None:
        slot, answer_type, accepted = simple
        if isinstance(value, accepted):
            return {"type": answer_type, slot: value}, None
        return None, TYPE
    # matrices, rankings, tables and the like: the typed object only
    return None, TYPE


def _answer(
    field: Any, field_id: str, value: Any, problems: _Problems, item: Optional[int]
) -> Optional[Dict[str, Any]]:
    if _kind(field) in UNSUPPORTED_TYPES:
        problems.add(field_id, NOT_SUPPORTED, item)
        return None
    simple = _SIMPLE.get(_kind(field))
    if (
        isinstance(value, dict)
        and simple is not None
        and simple[2] == (dict,)
        and not set(value) & (_TYPED_SLOTS | FORBIDDEN_SLOTS | {"type"})
    ):
        # an object of the question's own parts (a currency's code and amount,
        # a range's start and end, an address's street ...): the shorthand
        answer, code = _shorthand(field, value)
        if code:
            problems.add(field_id, code, item)
        return answer
    if isinstance(value, dict):
        code = _typed(value)
        if code:
            problems.add(field_id, code, item)
            return None
        return dict(value)
    answer, code = _shorthand(field, value)
    if code:
        problems.add(field_id, code, item)
    return answer


def _group(
    field: Any, field_id: str, value: Any, problems: _Problems
) -> Optional[Dict[str, Any]]:
    """A repeating group's answer: its typed object (``{"type": "group",
    "items": [...]}``) or the list of items; each item's answers are keyed by
    the group's question ids, each value read like a top-level one."""
    items = value.get("items") if isinstance(value, dict) else value
    if isinstance(value, dict) and not set(value) <= {"type", "items"}:
        problems.add(field_id, TYPE)
        return None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        problems.add(field_id, TYPE)
        return None
    children = {str(c.id): c for c in _children(field) if getattr(c, "id", None)}
    built: List[Dict[str, Any]] = []
    for position, item in enumerate(items):
        row: Dict[str, Any] = {}
        for child_id, child_value in item.items():
            child = children.get(str(child_id))
            if child is None:
                problems.add(str(child_id), UNKNOWN_FIELD, position)
                continue
            if child_value is None:
                continue
            answer = _answer(child, str(child_id), child_value, problems, position)
            if answer is not None:
                row[str(child_id)] = answer
        built.append(row)
    return {"type": "group", "items": built}


CLEAR_NOT_SUPPORTED = "clear_not_supported"


def build_answers(
    form: Any, raw: Dict[str, Any], allow_null: bool = True
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """(typed answers, problems) for the caller's ``raw`` answers against
    ``form`` (the published version). A ``None`` value is an unanswered
    question and is left out (``allow_null=False``, for an update, where a
    ``null`` would silently change nothing: reported as ``clear_not_supported``).
    An id that is not a question of the form is reported as
    ``unknown_field``, as for a respondent."""
    problems = _Problems()
    index = question_index(form)
    answers: Dict[str, Dict[str, Any]] = {}
    for key, value in raw.items():
        field_id = str(key)
        if value is None:
            if not allow_null:
                problems.add(field_id, CLEAR_NOT_SUPPORTED)
            continue
        field = index.get(field_id)
        if field is None:
            problems.add(field_id, UNKNOWN_FIELD)
            continue
        if is_repeating_group(field):
            answer = _group(field, field_id, value, problems)
        else:
            answer = _answer(field, field_id, value, problems, None)
        if answer is not None:
            answers[field_id] = answer
    return answers, problems.items
