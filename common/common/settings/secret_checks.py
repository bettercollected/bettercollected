"""Per-key checks for secret values the store accepts (standard library only).

``Registry.validate`` runs the check named by a secret's ``format`` when the
registry was built with ``format_checks`` (the admin portal and host commands
do; the services that only READ the store never refuse a row for its format, so
a value stored earlier cannot stop them from starting). A check returns ``None``
for a usable value or ``(code, message)``: a short refusal code and a sentence
that names the problem, never the value.

Formats:

``token``       shared secrets (JWT signing key, internal service keys): at least
                32 characters, not a known placeholder, not a repeating pattern,
                and not low-entropy. ``openssl rand -hex 32`` (what the deploy
                scripts generate) and any long random string pass.
``fernet``      a Fernet key: url-safe base64 of 32 bytes that are not all alike.
``key_pairs``   ``id:secret`` pairs separated by commas (edge assertion keys): an
                identifier of letters, digits and ``._-`` and a secret of at
                least 16 characters per pair.
``secret_list`` one or two comma separated secrets of at least 16 characters
                (webhook secrets: current first, previous second).

A Tink keyset (``tink_keyset``) needs Tink, which this package may not import:
the caller supplies that check (see ``backend.admin.services.settings_store``).
"""

from __future__ import annotations

import base64
import binascii
import math
import re
from collections import Counter
from typing import Callable, Dict, Optional, Tuple

Problem = Tuple[str, str]
FormatCheck = Callable[[str], Optional[Problem]]

MIN_TOKEN_CHARS = 32
MIN_LIST_SECRET_CHARS = 16
MIN_DISTINCT_CHARS = 8
MIN_ENTROPY_BITS = 2.5
PLACEHOLDERS = frozenset(
    {
        "random_api_key", "not-needed", "changeme", "change-me", "change_me", "secret",
        "password", "default", "example", "test", "your-secret-here", "your_secret_here",
        "replace-me", "replace_me", "todo", "xxxxxxxx",
    }
)
_PAIR_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_NO_SPACE = re.compile(r"^\S+$")


def _entropy(text: str) -> float:
    total = len(text)
    return -sum(n / total * math.log2(n / total) for n in Counter(text).values())


def _repeats(text: str) -> bool:
    """The text is one short unit repeated (``abcabcabc...``)."""
    for size in range(1, len(text) // 2 + 1):
        if len(text) % size == 0 and text == text[:size] * (len(text) // size):
            return True
    return False


def check_token(value: str) -> Optional[Problem]:
    if value.strip().lower() in PLACEHOLDERS:
        return "placeholder", "is a placeholder, not a secret"
    if len(value) < MIN_TOKEN_CHARS:
        return "too_short", f"must be at least {MIN_TOKEN_CHARS} characters (use `openssl rand -hex 32`)"
    if (
        len(set(value)) < MIN_DISTINCT_CHARS
        or _entropy(value) < MIN_ENTROPY_BITS
        or _repeats(value)
    ):
        return "low_entropy", "does not look random (use `openssl rand -hex 32`)"
    return None


def check_fernet(value: str) -> Optional[Problem]:
    try:
        raw = base64.urlsafe_b64decode(value)
    except (binascii.Error, ValueError):
        raw = b""
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode() != value:
        return "not_fernet", "is not a Fernet key (32 random bytes, url-safe base64)"
    if len(set(raw)) < MIN_DISTINCT_CHARS:
        return "low_entropy", "does not look random (32 bytes that are nearly all alike)"
    return None


def check_key_pairs(value: str) -> Optional[Problem]:
    items = value.split(",")
    if not 1 <= len(items) <= 16:
        return "bad_pairs", "must be 1 to 16 id:secret pairs separated by commas"
    seen = set()
    for item in items:
        ident, sep, secret = item.partition(":")
        if (
            not sep
            or not _PAIR_ID.match(ident)
            or not _NO_SPACE.match(secret)
            or len(secret) < MIN_LIST_SECRET_CHARS
        ):
            return "bad_pairs", f"each pair must be id:secret (secret at least {MIN_LIST_SECRET_CHARS} characters, no spaces)"
        if ident in seen:
            return "bad_pairs", "the same id appears twice"
        seen.add(ident)
    return None


def check_secret_list(value: str) -> Optional[Problem]:
    items = value.split(",")
    if not 1 <= len(items) <= 2:
        return "bad_list", "must be the current secret, and optionally the previous one after a comma"
    for item in items:
        if not _NO_SPACE.match(item) or len(item) < MIN_LIST_SECRET_CHARS:
            return "bad_list", f"each secret must be at least {MIN_LIST_SECRET_CHARS} characters without spaces"
    return None


FORMAT_CHECKS: Dict[str, FormatCheck] = {
    "token": check_token,
    "fernet": check_fernet,
    "key_pairs": check_key_pairs,
    "secret_list": check_secret_list,
}
# every secret format a spec may name; ``tink_keyset`` is supplied by the caller
SECRET_FORMATS = frozenset(FORMAT_CHECKS) | {"tink_keyset"}
