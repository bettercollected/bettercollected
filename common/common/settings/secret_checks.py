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
``identity_key`` the respondent identity key: hex or base64 text that decodes to
                at least 32 random-looking bytes (``openssl rand -hex 32``); the
                rules are in ``decode_identity_key``, the one place the text
                becomes key bytes.
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


MIN_IDENTITY_KEY_BYTES = 32
MIN_IDENTITY_DISTINCT_BYTES = 16
MIN_IDENTITY_ENTROPY_BITS = 4.0  # per byte; 32 random bytes measure 4.4 to 5.0
MIN_IDENTITY_TEXT_CLASSES = 2
_HEX = re.compile(r"^[0-9a-fA-F]+$")


def _looks_weak(raw: bytes) -> bool:
    """Bytes that cannot be 32 or more random bytes: too few distinct values,
    a repeated block (``"0123456789abcdef" * 4``), a counting sequence
    (``00 01 02 ...``) or a low bits-per-byte entropy."""
    if len(set(raw)) < max(MIN_DISTINCT_CHARS, MIN_IDENTITY_DISTINCT_BYTES):
        return True
    if _repeats(raw):
        return True
    steps = {(b - a) % 256 for a, b in zip(raw, raw[1:])}
    if len(steps) == 1:
        return True
    return _entropy(raw) < MIN_IDENTITY_ENTROPY_BITS


def decode_identity_key(value: str) -> Optional[bytes]:
    """The key bytes of a respondent identity key, or ``None`` when it is not
    usable. These rules define the key forever (the stored identities depend on
    the exact bytes), so they are fixed:

    1. Surrounding whitespace is ignored; nothing else is.
    2. Text of only hex digits is HEX and must have an even length
       (``openssl rand -hex 32`` prints 64 digits for its 32 bytes). Hex always
       wins: such text is never read as base64.
    3. Any other text is BASE64, standard (``+/``) or url-safe (``-_``) alphabet,
       padding optional; anything else is refused.
    4. The decoded bytes are the key. There must be at least 32 and they must
       look random: at least 16 distinct byte values, no repeated block, not a
       counting sequence, at least 4.0 bits of entropy per byte. A base64 text
       must also mix at least two of lower case, upper case, digits and symbols
       (a plain lower-case passphrase that happens to decode is refused).
    """
    text = (value or "").strip()
    if _HEX.match(text):
        if len(text) % 2:
            return None
        raw = bytes.fromhex(text)
    else:
        try:
            padded = text + "=" * (-len(text) % 4)
            raw = base64.b64decode(padded.replace("-", "+").replace("_", "/"), validate=True)
        except (binascii.Error, ValueError):
            return None
        classes = sum(
            any(test(c) for c in text)
            for test in (str.islower, str.isupper, str.isdigit, lambda c: c in "+/-_")
        )
        if classes < MIN_IDENTITY_TEXT_CLASSES:
            return None
    if len(raw) < MIN_IDENTITY_KEY_BYTES or _looks_weak(raw):
        return None
    return raw


def check_identity_key(value: str) -> Optional[Problem]:
    if value.strip().lower() in PLACEHOLDERS:
        return "placeholder", "is a placeholder, not a secret"
    if decode_identity_key(value) is None:
        return (
            "not_identity_key",
            f"must be hex or base64 text of at least {MIN_IDENTITY_KEY_BYTES} random bytes (use `openssl rand -hex 32`)",
        )
    return None


FORMAT_CHECKS: Dict[str, FormatCheck] = {
    "token": check_token,
    "fernet": check_fernet,
    "key_pairs": check_key_pairs,
    "secret_list": check_secret_list,
    "identity_key": check_identity_key,
}
# every secret format a spec may name; ``tink_keyset`` is supplied by the caller
SECRET_FORMATS = frozenset(FORMAT_CHECKS) | {"tink_keyset"}
