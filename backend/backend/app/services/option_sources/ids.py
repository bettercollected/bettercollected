"""The ids of options that come from a source.

A list item has a random id the server made (``li`` + 22 hex digits), kept
through renames and re-imports. An option built from another form's answers
has a **keyed hash** of its normalised label, scoped to workspace + form +
question (``fa`` + 22 hex digits): the same label always gets the same id (so
an answer can be matched later), and a log, a URL or an event that holds an id
reveals no label and cannot be confirmed by guessing names (HMAC under a key
derived from ``AUTH_JWT_SECRET`` with a purpose label of its own).

``AUTH_JWT_SECRET`` is a key ring (``<current>[,<previous>]``,
docs/auth-key-rotation.md). An id is stored in a response, so it cannot follow
a ring: it is keyed with the **primary** member only, and is the same whatever
the ring's other members are (adding a key, or dropping the old one, changes
nothing). A promote changes the primary, so options built afterwards have new
ids; a response keeps the id (and the label snapshot) it was made with.
``answer_option_ids`` gives an option's id under every member, which is what
an erasure note holds so it still matches choices made under an earlier key.
"""

import hashlib
import hmac
import re
import secrets
from typing import List

from common.settings import key_ring

LIST_PREFIX = "li"
ANSWER_PREFIX = "fa"
_ID_BODY = 22
_PURPOSE = b"bettercollected/option-source-id/v1"
_SHAPE = re.compile(r"(li|fa)[0-9a-f]{22}")


def new_item_id() -> str:
    return LIST_PREFIX + secrets.token_hex(_ID_BODY // 2)


def is_source_id(value: object) -> bool:
    return isinstance(value, str) and _SHAPE.fullmatch(value) is not None


class NoIdKey(RuntimeError):
    """The server has no secret to key option ids with (an empty
    ``AUTH_JWT_SECRET``): options from another form's answers are not built."""


def _keys() -> List[bytes]:
    """One key per member of the JWT ring, current first."""
    from backend.config import settings

    members = key_ring.token_members(settings.auth_settings.JWT_SECRET)
    if not members:
        raise NoIdKey("no secret to key option ids with")
    return key_ring.derive_all(members, _PURPOSE)


def _message(
    workspace_id: object, form_id: object, question_id: object, folded_label: str
) -> bytes:
    return "\0".join(
        (
            "form_answers",
            str(workspace_id),
            str(form_id),
            str(question_id),
            folded_label,
        )
    ).encode("utf-8")


def _id(key: bytes, message: bytes) -> str:
    return ANSWER_PREFIX + hmac.new(key, message, hashlib.sha256).hexdigest()[:_ID_BODY]


def answer_option_id(
    workspace_id: object, form_id: object, question_id: object, folded_label: str
) -> str:
    """The id of the option whose normalised (folded) label is given, keyed
    with the primary member of the JWT ring."""
    message = _message(workspace_id, form_id, question_id, folded_label)
    return _id(_keys()[0], message)


def answer_option_ids(
    workspace_id: object, form_id: object, question_id: object, folded_label: str
) -> List[str]:
    """The option's id under every member of the ring (primary first)."""
    message = _message(workspace_id, form_id, question_id, folded_label)
    return [_id(key, message) for key in _keys()]
