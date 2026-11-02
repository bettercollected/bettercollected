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

``GATED_TYPES`` is the one list of types behind the switch (time, day, currency,
date range and tags), and ``signature`` is what
counts as "the question's type and settings".

The signature question and the address question have a switch of their own,
``SIGNATURE_QUESTION_ENABLED`` (``SIGNATURE_TYPES``, refusal code
``signature_question_disabled``) and ``ADDRESS_QUESTION_ENABLED``
(``ADDRESS_TYPES``, refusal code ``address_question_disabled``). They run
through the same checks: a ``Gate`` names a switch, its types and its refusal,
``GATES`` lists them all, and every entry point below looks at each gate that is
off. A new gated type with its own switch is one more ``Gate``.
"""

import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Tuple

from backend.app.exceptions import HTTPException
from backend.app.services.calculated_fields import _get, _type

DISABLED_CODE = "question_type_disabled"
ADDRESS_DISABLED_CODE = "address_question_disabled"
SIGNATURE_DISABLED_CODE = "signature_question_disabled"
# Types behind the switch. Keep in step with GATED_TYPES in
# webapp/src/lib/form-ops/new-question-types.ts.
GATED_TYPES = frozenset({"time", "day", "currency", "date_range", "tags"})
# The address question's own switch (ADDRESS_QUESTION_ENABLED).
ADDRESS_TYPES = frozenset({"address"})
# The signature question's own switch (SIGNATURE_QUESTION_ENABLED).
SIGNATURE_TYPES = frozenset({"signature"})
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
        "splice_fields",
    }
)
PROBLEMS_MAX = 50

DISABLED_MESSAGE = (
    "These question types (time, day, currency, date range and tags) cannot be added or changed "
    "on this server yet (NEW_QUESTION_TYPES_ENABLED is off). Questions of these "
    "types that a form already has are kept."
)


ADDRESS_DISABLED_MESSAGE = (
    "The address question cannot be added or changed on this server yet "
    "(ADDRESS_QUESTION_ENABLED is off). An address question that a form "
    "already has is kept."
)


SIGNATURE_DISABLED_MESSAGE = (
    "The signature question cannot be added or changed on this server yet "
    "(SIGNATURE_QUESTION_ENABLED is off). A signature question that a form "
    "already has is kept."
)


def new_question_types_enabled() -> bool:
    """Is ``NEW_QUESTION_TYPES_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "NEW_QUESTION_TYPES_ENABLED", False))


def address_question_enabled() -> bool:
    """Is ``ADDRESS_QUESTION_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "ADDRESS_QUESTION_ENABLED", False))
def signature_question_enabled() -> bool:
    """Is ``SIGNATURE_QUESTION_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "SIGNATURE_QUESTION_ENABLED", False))


@dataclass(frozen=True)
class Gate:
    """A switch, the question types behind it and what a refused write says."""

    setting: str
    types: FrozenSet[str]
    code: str
    message: str
    enabled: Callable[[], bool]


NEW_TYPES_GATE = Gate(
    "NEW_QUESTION_TYPES_ENABLED",
    GATED_TYPES,
    DISABLED_CODE,
    DISABLED_MESSAGE,
    lambda: new_question_types_enabled(),
)
ADDRESS_GATE = Gate(
    "ADDRESS_QUESTION_ENABLED",
    ADDRESS_TYPES,
    ADDRESS_DISABLED_CODE,
    ADDRESS_DISABLED_MESSAGE,
    lambda: address_question_enabled(),
)
SIGNATURE_GATE = Gate(
    "SIGNATURE_QUESTION_ENABLED",
    SIGNATURE_TYPES,
    SIGNATURE_DISABLED_CODE,
    SIGNATURE_DISABLED_MESSAGE,
    lambda: signature_question_enabled(),
)
GATES = (NEW_TYPES_GATE, ADDRESS_GATE, SIGNATURE_GATE)
# Every type behind a switch.
ALL_GATED_TYPES = GATED_TYPES | ADDRESS_TYPES | SIGNATURE_TYPES


def gates_off() -> List[Gate]:
    """The gates whose switch is off."""
    return [gate for gate in GATES if not gate.enabled()]


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


def signature_parts(field: Any) -> Tuple[str, Tuple[str, ...]]:
    """What makes a gated question the same one, in two parts: the settings
    that belong to the type as one text (the type, the time limits, the
    currencies, the amount limits, the number and length of tags), and its date
    rules (of a day or a date range) one text each. Its title, its place and
    the settings every question has do not count."""
    props = _get(field, "properties")
    validations = _get(field, "validations")
    base = json.dumps(
        {
            "type": _type(field),
            "minTime": _get(props, "min_time"),
            "maxTime": _get(props, "max_time"),
            "currencies": _get(props, "currencies"),
            # an address question: the countries and whether street and city
            # are looked up
            "countries": _get(props, "countries"),
            "addressLookup": _get(props, "address_lookup"),
            "minValue": _get(validations, "min_value"),
            "maxValue": _get(validations, "max_value"),
            # a tags question: the number of tags and the length of one
            "minChoices": _get(validations, "min_choices"),
            "maxChoices": _get(validations, "max_choices"),
            "maxLength": _get(validations, "max_length"),
        },
        sort_keys=True,
        default=str,
    )
    rules = tuple(
        json.dumps(_plain(rule), sort_keys=True, default=str)
        for rule in _get(props, "date_rules") or []
    )
    return base, rules


def signature(field: Any) -> str:
    """The two parts of ``signature_parts`` as one text."""
    base, rules = signature_parts(field)
    return json.dumps([base, list(rules)])


Signatures = Dict[str, List[Tuple[str, Tuple[str, ...]]]]


def gated_signatures(form: Any) -> Signatures:
    """``{question id: [parts, ...]}`` of the gated questions of ``form`` (a
    list, because a document may carry one id twice: each copy counts)."""
    found: Signatures = {}
    for field in _walk(form):
        if _type(field) in ALL_GATED_TYPES:
            found.setdefault(str(_get(field, "id")), []).append(signature_parts(field))
    return found


def _covers(stored: Tuple[str, Tuple[str, ...]], now: Tuple[str, Tuple[str, ...]]) -> bool:
    """Is a question as it is now what was stored, or less: the same settings
    and no date rule the stored one did not have? Taking a date rule away
    (the date question it compared with was removed, say) asks nothing new of
    the server."""
    return stored[0] == now[0] and set(now[1]) <= set(stored[1])


def new_or_changed_questions(
    form: Any,
    existing: Any = None,
    stored: Optional[Signatures] = None,
    gate: Gate = NEW_TYPES_GATE,
) -> List[Tuple[str, str]]:
    """``(question id, type)`` of the gated questions of ``form`` that
    ``existing`` (the stored version, or None) does not have, on a question of
    the same id, with the same type and settings (a date rule may be fewer, not
    more). ``stored`` is ``gated_signatures(existing)`` when the caller has it.
    A stored question covers one question of ``form`` only: a second one with
    the same id reads as new. ``gate``: which types to look at."""
    if stored is None:
        stored = gated_signatures(existing) if existing is not None else {}
    remaining = {key: list(values) for key, values in stored.items()}
    changed: List[Tuple[str, str]] = []
    # the walk order is the document's: copies of an id are told apart by it
    for field in _walk(form):
        if _type(field) not in gate.types:
            continue
        key, parts = str(_get(field, "id")), signature_parts(field)
        match = next((i for i, kept in enumerate(remaining.get(key, [])) if _covers(kept, parts)), None)
        if match is not None:
            remaining[key].pop(match)
        else:
            changed.append((key, str(_type(field))))
    return changed


def ensure_question_types_allowed(form: Any, existing: Any = None) -> None:
    """While a switch is off, refuse (422, with the code of the gate that is
    off, e.g. ``question_type_disabled`` or ``address_question_disabled``) a save that brings a new gated question
    or changes the type or settings of one. Questions stored and unchanged
    pass. The layout containers' switch (``LAYOUT_CONTAINERS_ENABLED``,
    services/layout_containers.py) is checked here too, as every save path
    already ends in this function."""
    for gate in gates_off():
        changed = new_or_changed_questions(form, existing, gate=gate)
        if changed:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={
                    "code": gate.code,
                    "message": gate.message,
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
    from backend.app.services.layout_containers import ensure_layout_allowed

    ensure_layout_allowed(form, existing)


def _mentions_gated_type(value: Any) -> bool:
    """Does an operation's payload name a gated type anywhere (a field's
    ``type``)? Iterative: payloads can be deeply nested."""
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            kind = node.get("type")
            # a type is text: `type` may be anything in a payload (an expression)
            if isinstance(kind, str) and kind in ALL_GATED_TYPES:
                return True
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return False


def op_may_gate(op: Any, started: Signatures) -> bool:
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
    except (ValueError, TypeError):
        # a payload that cannot be dumped (nested too deeply, an expression):
        # be careful
        return True
    if _mentions_gated_type(payload):
        return True
    if name == "duplicate_page":
        return bool(started)
    targets = [payload.get("fieldId")]
    field = payload.get("field")
    if isinstance(field, dict):
        targets.append(field.get("id"))
    return any(isinstance(target, str) and target in started for target in targets)


def question_type_problem(
    form: Any, stored: Signatures, op_name: str
) -> Optional[str]:
    """For the edit operations: the refusal an operation earns when it left
    ``form`` with a gated question that is new or changed against ``stored``
    (``gated_signatures`` of the form the batch started from), or None. Always
    None while the switches are on or for an operation that cannot do it."""
    if op_name not in GATED_OPS:
        return None
    for gate in gates_off():
        if new_or_changed_questions(form, None, stored, gate):
            return gate.message
    return None
