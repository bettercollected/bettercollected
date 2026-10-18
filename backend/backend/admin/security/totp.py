"""Time-based one-time passwords (RFC 6238; HMAC-SHA-1, 6 digits, 30 s step).

Pure functions on the standard library. Replay protection is split in two:
``next_last_used_step`` is the pure decision, and the store that persists
``last_used_step`` must apply it atomically. Contract for that store::

    UPDATE factor SET last_used_step = :matched
     WHERE id = :id AND (last_used_step IS NULL OR last_used_step < :matched)

A code is accepted only when that statement changed exactly one row; two
concurrent submissions of the same code then cannot both succeed.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
from typing import Optional
from urllib.parse import quote, urlencode

from backend.admin.security.clock import Clock

DIGITS = 6
STEP_SECONDS = 30
DRIFT_STEPS = 1
SECRET_BYTES = 20  # 160 bits


def generate_secret() -> str:
    """A new random shared secret: base32, no padding (32 characters)."""
    raw = secrets.token_bytes(SECRET_BYTES)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def decode_secret(secret: str) -> bytes:
    """Raw key bytes of a base32 secret (case, spaces and padding tolerated).

    Raises ValueError for anything that is not valid base32."""
    cleaned = "".join(secret.split()).upper().rstrip("=")
    if not cleaned:
        raise ValueError("empty secret")
    padded = cleaned + "=" * (-len(cleaned) % 8)
    try:
        return base64.b32decode(padded, casefold=False)
    except (binascii.Error, ValueError):
        raise ValueError("invalid base32 secret") from None


def step_for(timestamp: float, step_seconds: int = STEP_SECONDS) -> int:
    return int(timestamp // step_seconds)


def hotp(key: bytes, counter: int, digits: int = DIGITS) -> str:
    """RFC 4226 HOTP with HMAC-SHA-1."""
    if counter < 0:
        raise ValueError("counter must not be negative")
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**digits)).zfill(digits)


def code_at(secret: str, timestamp: float, digits: int = DIGITS) -> str:
    """The code valid at ``timestamp``."""
    return hotp(decode_secret(secret), step_for(timestamp), digits)


def current_code(secret: str, clock: Clock) -> str:
    return code_at(secret, clock.time())


def verify(
    secret: str,
    code: str,
    clock: Clock,
    drift: int = DRIFT_STEPS,
) -> Optional[int]:
    """The matched step when ``code`` is valid within +-``drift`` steps, else None.

    Never raises on malformed input (wrong length, non-digits, bad secret).
    Every candidate step is compared, in constant time, whatever an earlier
    one gave."""
    candidate = "".join(str(code).split())
    if len(candidate) != DIGITS or not (candidate.isascii() and candidate.isdigit()):
        return None
    try:
        key = decode_secret(secret)
    except ValueError:
        return None
    now_step = step_for(clock.time())
    matched: Optional[int] = None
    for step in range(now_step - drift, now_step + drift + 1):
        if step < 0:
            continue
        if hmac.compare_digest(hotp(key, step), candidate) and matched is None:
            matched = step
    return matched


def next_last_used_step(
    last_used_step: Optional[int], matched_step: int
) -> Optional[int]:
    """The ``last_used_step`` to store, or None when the code is a replay
    (its step is not newer than the last accepted one)."""
    if last_used_step is not None and matched_step <= last_used_step:
        return None
    return matched_step


def otpauth_uri(secret: str, account: str, issuer: str) -> str:
    """The ``otpauth://totp`` provisioning URI for an authenticator app."""
    label = f"{quote(issuer, safe='')}:{quote(account, safe='')}"
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": STEP_SECONDS,
        },
        quote_via=quote,
    )
    return f"otpauth://totp/{label}?{query}"
