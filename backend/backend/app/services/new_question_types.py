"""The switch for the newer question types: ``NEW_QUESTION_TYPES_ENABLED``.

A creator-configurable feature that is not released yet stays off. While the
setting is off (the default), every write that would give a form a question
of one of these types, or change the type or the settings of one that is
there, is refused (422 ``question_type_disabled``). That is the builder's
save, the spec API, the edit operations (both engines), MCP and AI, a
template and an import: all of them end in ``ensure_question_types_allowed``
or, for operations, ``question_type_problem``.

What a form already holds keeps working: such a question renders, takes
answers, is exported and shown with the response, and a save that leaves its
type and settings as they are (a new title, a moved question, another
question changed) passes. Stored data is never touched.

``GATED_TYPES`` is the one list of types behind the switch (time, day and
currency now; the date range and tags join it), and ``signature`` is what
counts as "the question's type and settings".
"""

import json
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.app.exceptions import HTTPException
from backend.app.services.calculated_fields import _get, _type

DISABLED_CODE = "question_type_disabled"
# Types behind the switch. Keep in step with GATED_TYPES in
# webapp/src/lib/form-ops/new-question-types.ts.
GATED_TYPES = frozenset({"time", "day", "currency"})
# Operations that can give a form such a question or change one.
GATED_OPS = frozenset(
    {
        "add_field",
        "add_group",
        "add_page",
        "duplicate_page",
        "update_field",
        "set_field_validation",
        "insert_field",
        "insert_page",
        "replace_field",
    }
)
PROBLEMS_MAX = 50

DISABLED_MESSAGE = (
    "These question types (time, day and currency) cannot be added or changed "
    "on this server yet (NEW_QUESTION_TYPES_ENABLED is off). Questions of these "
    "types that a form already has are kept."
)


def new_question_types_enabled() -> bool:
    """Is ``NEW_QUESTION_TYPES_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "NEW_QUESTION_TYPES_ENABLED", False))


def _walk(form: Any) -> Iterable[Any]:
    pending = list(_get(form, "fields") or [])
    while pending:
        field = pending.pop()
        yield field
        pending.extend(_get(_get(field, "properties"), "fields") or [])


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items() if v is not None}
    return value


def signature(field: Any) -> str:
    """What makes a gated question the same one: its type and the settings
    that belong to the type (the time limits, the currencies, the date rules
    of a day, the amount limits). Its title, its place and the settings every
    question has do not count."""
    props = _get(field, "properties")
    validations = _get(field, "validations")
    return json.dumps(
        {
            "type": _type(field),
            "minTime": _get(props, "min_time"),
            "maxTime": _get(props, "max_time"),
            "currencies": _get(props, "currencies"),
            "dateRules": _plain(_get(props, "date_rules")),
            "minValue": _get(validations, "min_value"),
            "maxValue": _get(validations, "max_value"),
        },
        sort_keys=True,
        default=str,
    )


def gated_signatures(form: Any) -> Dict[str, str]:
    """``{question id: signature}`` of the gated questions of ``form``."""
    return {
        str(_get(field, "id")): signature(field)
        for field in _walk(form)
        if _type(field) in GATED_TYPES
    }


def new_or_changed_questions(
    form: Any, existing: Any = None, stored: Optional[Dict[str, str]] = None
) -> List[Tuple[str, str]]:
    """``(question id, type)`` of the gated questions of ``form`` that
    ``existing`` (the stored version, or None) does not have, on a question of
    the same id, with the same type and settings. ``stored`` is
    ``gated_signatures(existing)`` when the caller has it."""
    if stored is None:
        stored = gated_signatures(existing) if existing is not None else {}
    return [
        (str(_get(field, "id")), str(_type(field)))
        for field in _walk(form)
        if _type(field) in GATED_TYPES
        and stored.get(str(_get(field, "id"))) != signature(field)
    ]


def ensure_question_types_allowed(form: Any, existing: Any = None) -> None:
    """While the switch is off, refuse (422 ``question_type_disabled``) a save
    that brings a new gated question or changes the type or settings of one.
    Questions stored and unchanged pass."""
    if new_question_types_enabled():
        return
    changed = new_or_changed_questions(form, existing)
    if changed:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": DISABLED_CODE,
                "message": DISABLED_MESSAGE,
                "errors": [
                    {
                        "fieldId": field_id,
                        "type": field_type,
                        "message": f"The {field_type} question '{field_id}' is new or changed.",
                    }
                    for field_id, field_type in changed[:PROBLEMS_MAX]
                ],
            },
        )


def _mentions_gated_type(value: Any) -> bool:
    """Does an operation's payload name a gated type anywhere (a field's
    ``type``)? Iterative: payloads can be deeply nested."""
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get("type") in GATED_TYPES:
                return True
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return False


def op_may_gate(op: Any, started: Dict[str, str]) -> bool:
    """Can ``op`` leave a gated question new or changed? It can only when its
    payload names a gated type, or it targets a question that already has one
    (``started``: ``gated_signatures`` of the form the batch started from), or
    it copies a page while the form has any. A cheap look at the payload, so a
    batch on a large form needs no copy of the form per operation."""
    name = getattr(op, "op", None)
    if name not in GATED_OPS:
        return False
    try:
        payload = op.model_dump(mode="json", by_alias=True, exclude_none=True)
    except ValueError:
        # a payload nested too deeply to dump (an expression): be careful
        return True
    if _mentions_gated_type(payload):
        return True
    if name == "duplicate_page":
        return bool(started)
    targets = {payload.get("fieldId")}
    field = payload.get("field")
    if isinstance(field, dict):
        targets.add(field.get("id"))
    return any(target in started for target in targets if target)


def question_type_problem(
    form: Any, stored: Dict[str, str], op_name: str
) -> Optional[str]:
    """For the edit operations: the refusal an operation earns when it left
    ``form`` with a gated question that is new or changed against ``stored``
    (``gated_signatures`` of the form the batch started from), or None. Always
    None while the switch is on or for an operation that cannot do it."""
    if op_name not in GATED_OPS or new_question_types_enabled():
        return None
    return DISABLED_MESSAGE if new_or_changed_questions(form, None, stored) else None
