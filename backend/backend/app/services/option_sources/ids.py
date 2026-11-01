"""The ids of options that come from a source.

A list item has a random id the server made (``li`` + 22 hex digits), kept
through renames and re-imports. An option built from another form's answers
has a **keyed hash** of its normalised label, scoped to workspace + form +
question (``fa`` + 22 hex digits): the same label always gets the same id (so
an answer can be matched later), and a log, a URL or an event that holds an id
reveals no label and cannot be confirmed by guessing names (HMAC under a key
derived from ``AUTH_JWT_SECRET`` with a purpose label of its own). If that
secret is rotated the ids change; stored answers keep their label snapshot.
"""

import hashlib
import hmac
import re
import secrets

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


def _key() -> bytes:
    from backend.config import settings

    secret = settings.auth_settings.JWT_SECRET or ""
    if not secret:
        raise NoIdKey("no secret to key option ids with")
    return hmac.new(secret.encode("utf-8"), _PURPOSE, hashlib.sha256).digest()


def answer_option_id(
    workspace_id: object, form_id: object, question_id: object, folded_label: str
) -> str:
    """The id of the option whose normalised (folded) label is given."""
    message = "\0".join(
        (
            "form_answers",
            str(workspace_id),
            str(form_id),
            str(question_id),
            folded_label,
        )
    ).encode("utf-8")
    digest = hmac.new(_key(), message, hashlib.sha256).hexdigest()
    return ANSWER_PREFIX + digest[:_ID_BODY]
