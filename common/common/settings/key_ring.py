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
# appended to the fingerprint every build with key-ring support reports in its
# heartbeat (``settings.service_state.keyset_fp``, whose charset allows it): the
# ``authkeys.add_key`` task refuses while a live instance does not carry it, since
# a build from before rings would read "<old>,<new>" as one key
REPORT_MARK = ".r1"
MAX_MEMBERS = 2
# a member of a JWT ring is a token-format secret: at least this many characters
# (``check_token``). A value is read as a ring only when BOTH sides of its one comma
# are that long and free of whitespace, so a hand-made single secret that happens to
# contain a comma is still one secret
MIN_TOKEN_MEMBER = 32

__all__ = [
    "REPORT_MARK",
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


def _normalize(value: Optional[str]) -> str:
    """A Fernet key as an env file means it: trimmed, one pair of quotes removed
    (``common/configs/shipped_secrets.py`` ``normalize_secret``: the same rule)."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1].strip()
    return value


def fernet_members(value: Optional[str]) -> List[str]:
    """The Fernet keys of a ring, current first. A url-safe base64 key never
    contains a comma, so every comma separates two keys. Empty for no value.
    More than two members are returned as they are (the format check refuses
    them; a reader never silently drops a key). The one parser every use of the
    key goes through (the cipher, the PKCE verifiers, the sign-in code hash)."""
    text = _normalize(value)
    if not text:
        return []
    return [part.strip() for part in text.split(SEPARATOR)]


def token_members(value: Optional[str]) -> List[str]:
    """The signing secrets of a ring, current first: two when the value has
    exactly one comma and both sides are token-length secrets without
    whitespace. Any other value is ONE secret and is returned exactly as it is
    (not trimmed: a single secret signs, and keys the stored draft hashes, byte
    for byte as it did before rings existed). Empty for no value."""
    if value is None or not value.strip():
        return []
    parts = value.strip().split(SEPARATOR)
    if len(parts) == 2 and all(
        len(part) >= MIN_TOKEN_MEMBER and not any(c.isspace() for c in part)
        for part in parts
    ):
        return parts
    return [value]


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
