"""Key rings: ``AUTH_JWT_SECRET`` and ``AUTH_AES_HEX_KEY`` may hold one key or two.

A ring is ``<current>[,<previous>]`` (at most two members, current first). The
first member is the one that signs and encrypts; every member is accepted when
verifying and decrypting. That is what lets a rotation add the new key beside
the old one, promote it, re-encrypt, and only then retire the old one, with no
moment at which a stored value or a signed-in user is unreadable
(docs/auth-key-rotation.md).

A plain single key is a ring of one, so a stack that never rotates is unchanged.

Standard library only (``common.settings`` is a pure library). The same rule is
copied, with its own tests, in ``common/configs/shipped_secrets.py`` (which the
workers carry as identical copies); ``common/tests/test_key_ring.py`` keeps the
two in step.

The ring is a secret: nothing here logs, prints or puts a member in an error.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import List, Optional, Sequence

SEPARATOR = ","
MAX_MEMBERS = 2
# a member of a JWT ring is a token-format secret: at least this many characters
# (``check_token``). A value is read as a ring only when BOTH sides of its one comma
# are that long and free of whitespace, so a hand-made single secret that happens to
# contain a comma is still one secret
MIN_TOKEN_MEMBER = 32

__all__ = [
    "MAX_MEMBERS",
    "MIN_TOKEN_MEMBER",
    "SEPARATOR",
    "derive",
    "derive_all",
    "fernet_members",
    "join",
    "primary",
    "token_members",
]


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


def fernet_members(value: Optional[str]) -> List[str]:
    """The Fernet keys of a ring, current first. A url-safe base64 key never
    contains a comma, so every comma separates two keys. Empty for no value.
    More than two members are returned as they are (the format check refuses
    them; a reader never silently drops a key)."""
    text = _clean(value)
    if not text:
        return []
    return [part.strip() for part in text.split(SEPARATOR)]


def token_members(value: Optional[str]) -> List[str]:
    """The signing secrets of a ring, current first: two when the value has
    exactly one comma and both sides are token-length secrets without
    whitespace, otherwise the whole value as one secret."""
    text = _clean(value)
    if not text:
        return []
    parts = text.split(SEPARATOR)
    if len(parts) == 2 and all(
        len(part) >= MIN_TOKEN_MEMBER and not any(c.isspace() for c in part)
        for part in parts
    ):
        return parts
    return [text]


def primary(members: Sequence[str]) -> str:
    """The member that signs and encrypts (empty when there is none)."""
    return members[0] if members else ""


def join(members: Sequence[str]) -> str:
    """The stored text of a ring."""
    return SEPARATOR.join(members)


def derive(member: str, label: bytes) -> bytes:
    """The HMAC sub-key of one member for one purpose (the raw key is never used
    as an HMAC key itself). Member 0 mints, every member verifies."""
    return hmac.new(member.encode(), label, hashlib.sha256).digest()


def derive_all(members: Sequence[str], label: bytes) -> List[bytes]:
    return [derive(member, label) for member in members]
