"""Sign-in codes at rest: a keyed hash of the code, never the code.

The account's ``otp_code`` holds ``otp1$<wrong tries>$<hex HMAC-SHA256>``:

* the key is a sub-key of ``AUTH_AES_HEX_KEY``, HMAC(key, ``SUBKEY_LABEL``),
  so the raw key is never reused as an HMAC key. Rotating that key
  invalidates the codes pending at that moment (they live 5 minutes);
* the hashed message binds the code to the account's id (immutable, and never
  case-folded: Python's and Postgres' ``lower`` may disagree on an email), the
  purpose (``otp_code_for``: creator or respondent) and the expiry, so a stored
  value copied to another account, purpose or expiry never matches;
* the number of wrong tries travels with the hash: a new code starts at 0 and
  ``MAX_WRONG_TRIES`` wrong tries clear the code.

Anything else in ``otp_code`` (a plain code written before this format) is
not a valid code: :func:`parse` returns ``None`` and the caller refuses it.
Comparisons use :func:`hmac.compare_digest`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Optional

from auth.config import settings

#: Wrong tries before a code is cleared and a new one must be requested.
MAX_WRONG_TRIES = 5
SUBKEY_LABEL = b"bettercollected/auth/sign-in-code/v1"
_PREFIX = "otp1"
_STORED = re.compile(r"^otp1\$([0-9]{1,2})\$([0-9a-f]{64})$")


@dataclass(frozen=True)
class StoredCode:
    wrong_tries: int
    digest: str


def _key(secret: Optional[str]) -> bytes:
    secret = settings.AUTH_AES_HEX_KEY if secret is None else secret
    if not secret:
        raise RuntimeError("AUTH_AES_HEX_KEY is not set")
    return hmac.new(secret.encode(), SUBKEY_LABEL, hashlib.sha256).digest()


def digest(
    code: str,
    account_id: str,
    purpose: Optional[str],
    expiry: int,
    *,
    secret: Optional[str] = None,
) -> str:
    """The hex HMAC of ``code`` for this account (its id), purpose and expiry."""
    if not account_id:
        raise ValueError("a sign-in code is bound to an account id")
    message = json.dumps(
        [
            "v1",
            str(account_id),
            str(getattr(purpose, "value", purpose) or ""),
            int(expiry),
            code or "",
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hmac.new(_key(secret), message, hashlib.sha256).hexdigest()


def stored(code_digest: str, wrong_tries: int = 0) -> str:
    """The value kept in ``otp_code``."""
    return f"{_PREFIX}${int(wrong_tries)}${code_digest}"


def parse(value: Optional[str]) -> Optional[StoredCode]:
    """The stored hash and its wrong tries; ``None`` for anything else (a
    plain code from before this format, a damaged value)."""
    found = _STORED.match(value) if isinstance(value, str) else None
    if found is None:
        return None
    return StoredCode(wrong_tries=int(found.group(1)), digest=found.group(2))


def matches(
    expected: StoredCode,
    code: str,
    account_id: str,
    purpose: Optional[str],
    expiry: int,
    *,
    secret: Optional[str] = None,
) -> bool:
    """Whether ``code`` is the one hashed into ``expected`` (constant time)."""
    if not isinstance(code, str) or not code:
        return False
    candidate = digest(code, account_id, purpose, expiry, secret=secret)
    return hmac.compare_digest(candidate, expected.digest)
