"""The respondent identity: how an anonymous response is tied to the account
that submitted it, without storing the address.

``v2:`` + hex(HMAC-SHA256(key, md5_hex(email))), where ``md5_hex`` is exactly
what ``hash_string`` has always computed (the signed-in ``user.sub``, no other
normalisation) and ``key`` is ``RESPONDENT_IDENTITY_KEY``: a dedicated secret of
at least 32 random bytes, not derived from the Fernet or keyset material. The
MD5 is only an internal step, so a value stored before this scheme converts
without the address (``convert_legacy``); what stops anyone who knows an
address from computing the stored value is the key.

A stored value that does not start with ``v2:`` is a bug (the migration,
``backend.identity_rekey``, converts every stored value), and matching refuses
it: there is no MD5 fallback. Nothing here logs a value, a hash or a key.

Key rotation (not implemented, documented in docs/respondent-identity.md):
``HMAC(new, md5_hex)`` cannot be computed from ``HMAC(old, md5_hex)``, so a
rotation keeps the old key as a match fallback, upgrades a value when it
matches, and retires the old key once nothing is left on it.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

from common.settings.secret_checks import MIN_IDENTITY_KEY_BYTES, decode_identity_key
from loguru import logger

from backend.app.utils.hash import hash_string

PREFIX = "v2:"
KEY_NAME = "RESPONDENT_IDENTITY_KEY"
KEY_HINT = "openssl rand -hex 32"


#: HMAC-SHA256(key, this label) is what ``app.respondent_identity_key_check``
#: stores (0022): it says which key converted the stored identities without
#: being the key, and cannot be used to compute or match an identity.
KEY_CHECK_LABEL = b"bettercollected/respondent-identity/key-check/v1"
#: how often a non-v2 stored value may be logged (it should never happen, and a
#: request that hits one repeats)
WARN_INTERVAL_SECONDS = 300.0
_last_warning = [float("-inf")]


class IdentityKeyError(RuntimeError):
    """The respondent identity key is missing or unusable (never carries it)."""


class IdentityKeyMismatch(IdentityKeyError):
    """The configured key is not the one that converted the stored identities."""


class IdentityKeyUnconfirmed(IdentityKeyMismatch):
    """v2 identities are stored but no key check says which key made them."""


#: set once a pass has seen that the configured key is not the one that
#: converted the stored identities: nothing may then be written with it (a
#: second key in the data breaks matching for good). Cleared by a restart.
_key_mismatch_seen = [False]


def mark_key_mismatch() -> None:
    _key_mismatch_seen[0] = True


def key_mismatch_seen() -> bool:
    return _key_mismatch_seen[0]


def key_check_value(key: bytes) -> str:
    return hmac.new(key, KEY_CHECK_LABEL, hashlib.sha256).hexdigest()


def fingerprint_of(check_value: str) -> str:
    """The first 4 bytes of a key check value: enough to compare two keys by
    eye, useless for anything else."""
    return check_value[:8]


def key_bytes(configured: Optional[str]) -> bytes:
    """The HMAC key of the configured text; raises without echoing it."""
    raw = decode_identity_key(configured or "")
    if raw is None:
        raise IdentityKeyError(
            f"{KEY_NAME} is not set or is not usable: it must be hex or base64 text "
            f"of at least {MIN_IDENTITY_KEY_BYTES} random bytes (`{KEY_HINT}`)"
        )
    return raw


def configured_key() -> bytes:
    from backend.config import settings

    return key_bytes(settings.respondent_identity.KEY)


def require_identity_key(service: str, configured: Optional[str]) -> None:
    """Refuse to start ``service`` without a usable key."""
    try:
        key_bytes(configured)
    except IdentityKeyError as exc:
        raise IdentityKeyError(
            f"Refusing to start {service}: {exc}. Generate it once and set it as "
            f"{KEY_NAME} (environment or settings store); it is never derived from "
            "another key and a new value breaks every stored respondent identity. "
            "See docs/respondent-identity.md."
        ) from None


def is_v2(stored: Optional[str]) -> bool:
    return bool(stored) and stored.startswith(PREFIX)


def derive(key: bytes, legacy_md5_hex: str) -> str:
    """``v2:`` + HMAC-SHA256(key, md5_hex), lower-case hex."""
    mac = hmac.new(key, legacy_md5_hex.encode("utf-8"), hashlib.sha256)
    return PREFIX + mac.hexdigest()


def identity_of(email: str, key: Optional[bytes] = None) -> str:
    """The identity value stored for the signed-in ``email`` (``user.sub``).
    Refuses (:class:`IdentityKeyMismatch`) once the configured key is known to
    differ from the one the stored identities were converted with."""
    if key is None and _key_mismatch_seen[0]:
        raise IdentityKeyMismatch(
            "RESPONDENT_IDENTITY_KEY is not the key that converted the stored respondent "
            "identities; refusing to write or match identities with it (restart with the right key)"
        )
    return derive(key if key is not None else configured_key(), hash_string(email))


def convert_legacy(key: bytes, stored: str) -> str:
    """The v2 value of a stored legacy (MD5) value; a v2 value is returned as is."""
    return stored if is_v2(stored) else derive(key, stored)


def matches(stored: Optional[str], email: str, key: Optional[bytes] = None) -> bool:
    """Whether ``stored`` is the identity of ``email``. Constant time; a value
    that is empty or not ``v2:`` never matches (no MD5 fallback)."""
    if not stored:
        return False
    if not is_v2(stored):
        now = time.monotonic()
        if now - _last_warning[0] >= WARN_INTERVAL_SECONDS:
            _last_warning[0] = now
            logger.warning(
                "a stored respondent identity is not v2; refusing the match "
                "(logged at most once every {:.0f} s; run python -m backend.identity_rekey)",
                WARN_INTERVAL_SECONDS,
            )
        return False
    return hmac.compare_digest(stored.encode("utf-8"), identity_of(email, key).encode("utf-8"))
