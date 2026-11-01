"""The cursor of the responses list: where a page began, signed.

A keyset page is reached by seeking to a row, not by counting rows from the
start. Each page the list returns carries one opaque ``cursor`` naming its
first row; the client may send it back with a request for a page near that one
(next, previous, a few pages either way) and the server seeks to that row and
skips only the few pages in between.

The cursor is client-held, so it is tamper-safe by construction:

- **Signed** with HMAC-SHA256 under a key derived from the backend's
  ``AUTH_JWT_SECRET`` with a purpose label of its own (the same pattern as the
  other signed tokens). Without that secret no cursor is issued or accepted
  and the list still works from the start.
- **Bound** to the workspace, the form, the sort, the page size (all in the
  token) and the filters (in the signature only, never in the token: no
  filter value and nothing derived from the search text is readable in it), so a cursor from
  another form, another workspace, another sort or filter, or another page
  size is refused, not reinterpreted.
- **Typed**: even a correctly signed token is checked again (a timestamp, a
  24-hex id, an integer) before it is used, and the values only ever reach
  SQL as bound parameters.
- **Short-lived**: 24 hours; the client then asks without it.
"""

import base64
import datetime as dt
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from common.settings import key_ring

from backend.app.models.filter_queries.response_list import (
    KEYSET_SORTS,
    SORT_VERSION,
    ResponseListQuery,
)
from backend.config import settings

TOKEN_TTL = dt.timedelta(hours=24)
CLOCK_SKEW = dt.timedelta(minutes=2)
MAX_TOKEN_LENGTH = 2048
_VERSION = "c1"
_PURPOSE = b"bettercollected/response-list-cursor/v1"
_ID = re.compile(r"[0-9a-f]{24}")
_MAX_PAGE = 10_000_000


class InvalidCursor(ValueError):
    """The cursor is not one this server issued for this list (tampered,
    foreign, expired, or malformed)."""


@dataclass(frozen=True)
class Anchor:
    """The first row of page ``page``: the keyset values it sorts on."""

    page: int
    # (form version when sorting by version,) submitted at, id
    version: Optional[int]
    created_at: dt.datetime
    row_id: str

    def key(self) -> Tuple:
        head = (self.version,) if self.version is not None else ()
        return (*head, self.created_at, self.row_id)


def _keys() -> list:
    """The signing keys, one per member of the JWT key ring (current first;
    docs/auth-key-rotation.md): the first signs, every one verifies."""
    return key_ring.derive_all(
        key_ring.token_members(settings.auth_settings.JWT_SECRET), _PURPOSE
    )


def _key() -> Optional[bytes]:
    keys = _keys()
    return keys[0] if keys else None


def _verifies(token_signature: str, payload: str) -> bool:
    ok = False
    for key in _keys():
        ok = hmac.compare_digest(_sign(key, payload), token_signature) or ok
    return ok


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(key: bytes, payload: str) -> str:
    return _b64(hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest())


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _binding(workspace_id, form_id, query: ResponseListQuery) -> dict:
    return {
        "w": str(workspace_id),
        "f": str(form_id),
        "s": query.sort_by,
        "d": bool(query.descending),
        "z": query.size,
    }


def _signed_text(body: str, query: ResponseListQuery) -> str:
    """What the signature covers: the token, and the filters (search text
    included) it is for. The filters are *not* in the token: a hash of them
    in a readable token would let anyone who sees the address check guesses
    of the searched email offline. Under the HMAC key the same hash tells
    nothing, and a cursor used with other filters simply fails to verify."""
    return f"{body}|{query.filters.fingerprint()}"


def issue(
    workspace_id,
    form_id,
    query: ResponseListQuery,
    anchor: Anchor,
    now: Optional[dt.datetime] = None,
) -> Optional[str]:
    """The cursor for the page that begins at ``anchor``, or None when the
    server has no secret to sign it with."""
    key = _key()
    if key is None:
        return None
    claims = _binding(workspace_id, form_id, query)
    claims["p"] = anchor.page
    claims["t"] = _utc(anchor.created_at).isoformat(timespec="microseconds")
    claims["r"] = anchor.row_id
    if anchor.version is not None:
        claims["v"] = anchor.version
    claims["i"] = int(_utc(now or dt.datetime.now(dt.timezone.utc)).timestamp() * 1000)
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    body = f"{_VERSION}.{payload}"
    return f"{body}.{_sign(key, _signed_text(body, query))}"


def read(
    token: str,
    workspace_id,
    form_id,
    query: ResponseListQuery,
    now: Optional[dt.datetime] = None,
) -> Anchor:
    """The anchor in ``token``, if it is a valid, unexpired cursor for exactly
    this list; otherwise ``InvalidCursor``."""
    key = _key()
    if key is None or not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:
        raise InvalidCursor()
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _VERSION:
        raise InvalidCursor()
    body = f"{parts[0]}.{parts[1]}"
    try:
        if not _verifies(parts[2], _signed_text(body, query)):
            raise InvalidCursor()
        claims = json.loads(_unb64(parts[1]))
    except (ValueError, TypeError):
        raise InvalidCursor() from None
    if not isinstance(claims, dict):
        raise InvalidCursor()
    for name, value in _binding(workspace_id, form_id, query).items():
        if claims.get(name) != value:
            raise InvalidCursor()
    issued = claims.get("i")
    if not _is_int(issued):
        raise InvalidCursor()
    issued_at = dt.datetime.fromtimestamp(issued / 1000, tz=dt.timezone.utc)
    current = _utc(now or dt.datetime.now(dt.timezone.utc))
    if issued_at > current + CLOCK_SKEW or current - issued_at > TOKEN_TTL:
        raise InvalidCursor()
    page = claims.get("p")
    row_id = claims.get("r")
    stamp = claims.get("t")
    if not _is_int(page) or not 1 <= page <= _MAX_PAGE:
        raise InvalidCursor()
    if not isinstance(row_id, str) or not _ID.fullmatch(row_id):
        raise InvalidCursor()
    try:
        created_at = dt.datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        raise InvalidCursor() from None
    if created_at.tzinfo is None:
        raise InvalidCursor()
    version = claims.get("v")
    if query.sort_by == SORT_VERSION:
        if not _is_int(version) or not -(2**31) <= version < 2**31:
            raise InvalidCursor()
    elif version is not None or query.sort_by not in KEYSET_SORTS:
        raise InvalidCursor()
    return Anchor(
        page=page,
        version=version,
        created_at=_utc(created_at),
        row_id=row_id,
    )


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
