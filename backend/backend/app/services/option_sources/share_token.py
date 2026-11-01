"""Proof that a respondent's page showed the "your answer may be offered as a
choice" notice, for which questions.

A question with ``shareAsChoices`` on shows the respondent a notice next to it.
Whether a given respondent saw it cannot be read from the submission: someone
who loaded the form before the setting was published, who resumed an older
draft or who uses a client that never shows the notice did not see it, and
their answer must not be offered to anyone. So the public form fetch hands out
a signed token naming the questions whose notice the served version showed;
the form page sends it back with the submission, and the response is stamped
(``shared_as_choices``) with the questions of the token that the form's
current version still shares. No token, a bad, expired or foreign token: an
empty stamp (fail closed).

Same construction as ``services/ai/notice_token.py``: HMAC-SHA256 under a key
derived from ``AUTH_JWT_SECRET`` with a purpose label of its own, bound to the
workspace and form, valid for 24 hours. ``AUTH_JWT_SECRET`` is a key ring: the
first member signs, every member verifies, so a rotation never invalidates a
token in flight.
"""

import base64
import datetime as dt
import hashlib
import hmac
import json
from typing import Iterable, List, Optional

from common.settings import key_ring

from backend.config import settings

TOKEN_TTL = dt.timedelta(hours=24)
CLOCK_SKEW = dt.timedelta(minutes=2)
MAX_QUESTIONS = 100
# a question id longer than this is never named by a token (a form's ids are
# UUIDs or short keys): fail closed for that question
MAX_ID_LENGTH = 64
# the largest token that can be issued: base64 of the claims for MAX_QUESTIONS
# ids of MAX_ID_LENGTH (each with its quotes and comma), two ids and the
# timestamp with generous slack, plus the version and the signature. Used for
# the submit route's size cap, so a form at the question limit never 422s.
MAX_TOKEN_LENGTH = 4 * ((MAX_QUESTIONS * (MAX_ID_LENGTH + 3) + 512 + 2) // 3) + 64
_VERSION = "v1"
_PURPOSE = b"bettercollected/option-share-notice-token/v1"


def _keys() -> List[bytes]:
    """One signing key per member of the JWT key ring (current first): the
    first signs, every one verifies (docs/auth-key-rotation.md)."""
    return key_ring.derive_all(
        key_ring.token_members(settings.auth_settings.JWT_SECRET), _PURPOSE
    )


def _verifies(signature: str, payload: str) -> bool:
    ok = False
    for key in _keys():
        ok = hmac.compare_digest(_sign(key, payload), signature) or ok
    return ok


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _ms(value: dt.datetime) -> int:
    return int(_utc(value).timestamp() * 1000)


def _sign(key: bytes, payload: str) -> str:
    return _b64(hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest())


def issue_token(
    *,
    workspace_id,
    form_id,
    question_ids: Iterable[str],
    now: Optional[dt.datetime] = None,
) -> Optional[str]:
    """A token saying the notice of ``question_ids`` was shown now, or None
    when there is nothing shared or the server has no secret to sign with."""
    keys = _keys()
    ids = sorted(
        {str(q) for q in question_ids if len(str(q)) <= MAX_ID_LENGTH}
    )[:MAX_QUESTIONS]
    if not keys or not ids:
        return None
    key = keys[0]
    claims = {
        "w": str(workspace_id),
        "f": str(form_id),
        "q": ids,
        "i": _ms(now or dt.datetime.now(dt.timezone.utc)),
    }
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    body = f"{_VERSION}.{payload}"
    return f"{body}.{_sign(key, body)}"


def shown_question_ids(
    token: Optional[str],
    *,
    workspace_id,
    form_id,
    now: Optional[dt.datetime] = None,
) -> List[str]:
    """The questions whose notice ``token`` proves was shown, or ``[]`` when
    it is missing, forged, expired or for another form (never an error)."""
    if not _keys() or not token or not isinstance(token, str):
        return []
    if len(token) > MAX_TOKEN_LENGTH:
        return []
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _VERSION:
        return []
    body = f"{parts[0]}.{parts[1]}"
    try:
        if not _verifies(parts[2], body):
            return []
        claims = json.loads(_unb64(parts[1]))
    except (ValueError, TypeError):
        return []
    if not isinstance(claims, dict):
        return []
    if claims.get("w") != str(workspace_id) or claims.get("f") != str(form_id):
        return []
    issued_ms = claims.get("i")
    if not isinstance(issued_ms, int) or isinstance(issued_ms, bool):
        return []
    issued = dt.datetime.fromtimestamp(issued_ms / 1000, tz=dt.timezone.utc)
    current = _utc(now or dt.datetime.now(dt.timezone.utc))
    if issued > current + CLOCK_SKEW or current - issued > TOKEN_TTL:
        return []
    ids = claims.get("q")
    if not isinstance(ids, list):
        return []
    return [q for q in ids if isinstance(q, str)][:MAX_QUESTIONS]


def stamp(
    token: Optional[str], *, workspace_id, form_id, shared_now: Iterable[str]
) -> List[str]:
    """What a response is stamped with: the questions the page showed the
    notice for that the form's current version still shares."""
    shown = set(
        shown_question_ids(token, workspace_id=workspace_id, form_id=form_id)
    )
    return [q for q in shared_now if q in shown]
