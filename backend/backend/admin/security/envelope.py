"""Authenticated encryption of small secrets (AES-256-GCM).

Blob format: ``v1:<key_id>:<nonce>:<ciphertext>``; nonce (96 bits, random per
call) and ciphertext (with the 128-bit tag appended) are base64url without
padding. The caller supplies the 32-byte key and the associated data (for
example ``factor_id|email``), which binds a blob to its row: it does not
decrypt anywhere else. ``key_id`` names the key version so keys can rotate.
"""

import base64
import binascii
import os
import re
from typing import List, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = "v1"
VERSION_2 = "v2"
KEY_BYTES = 32
NONCE_BYTES = 12
_KEY_ID = re.compile(r"[A-Za-z0-9_.-]{1,32}")
_B64 = re.compile(r"[A-Za-z0-9_-]+")


class EnvelopeError(Exception):
    """A blob could not be produced or opened. Messages are fixed text:
    they never contain plaintext, keys, nonces or ciphertext."""


class UnsupportedVersion(EnvelopeError):
    """The blob is from a version this code does not know."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    if not _B64.fullmatch(text):
        raise EnvelopeError("malformed envelope")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError):
        raise EnvelopeError("malformed envelope") from None


def _check_key(key: bytes) -> None:
    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_BYTES:
        raise EnvelopeError("invalid key")


def _v1_aad(key_id: str, aad: bytes) -> bytes:
    """The AAD actually authenticated: format, key id, then the caller's, so a
    blob whose key id label is edited fails to open."""
    return b"v1|" + key_id.encode("ascii") + b"|" + aad


def encrypt(plaintext: bytes, key: bytes, key_id: str, aad: bytes) -> str:
    """Seal ``plaintext`` under ``key`` (32 bytes), bound to ``aad``."""
    _check_key(key)
    if not _KEY_ID.fullmatch(key_id):
        raise EnvelopeError("invalid key id")
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(bytes(key)).encrypt(nonce, plaintext, _v1_aad(key_id, aad))
    return f"{VERSION}:{key_id}:{_b64e(nonce)}:{_b64e(ciphertext)}"


def _split(blob: str) -> List[str]:
    if not isinstance(blob, str):
        raise EnvelopeError("malformed envelope")
    parts = blob.split(":")
    if not re.fullmatch(r"v[0-9]{1,3}", parts[0]):
        raise EnvelopeError("malformed envelope")
    if parts[0] not in (VERSION, VERSION_2):
        raise UnsupportedVersion("unsupported envelope version")
    return parts


def _fields(parts: List[str], count: int) -> List[bytes]:
    if len(parts) != count + 2 or not _KEY_ID.fullmatch(parts[1]):
        raise EnvelopeError("malformed envelope")
    return [_b64d(p) for p in parts[2:]]


def parse(blob: str) -> Tuple[str, str, bytes, bytes]:
    """``(version, key_id, nonce, ciphertext)`` of a v1 or v2 blob (for v2 the
    nonce and ciphertext are those of the value, ``key_id`` is the KEK id).

    Raises UnsupportedVersion for a well-formed version other than v1/v2 (a
    newer blob is reported, not mistaken for corruption) and EnvelopeError
    for anything else."""
    parts = _split(blob)
    if parts[0] == VERSION:
        nonce, ciphertext = _fields(parts, 2)
        if len(nonce) != NONCE_BYTES:
            raise EnvelopeError("malformed envelope")
        return parts[0], parts[1], nonce, ciphertext
    version, kek_id, _, _, nonce, ciphertext = parse_v2(blob)
    return version, kek_id, nonce, ciphertext


def key_id_of(blob: str) -> str:
    """The key id a blob was sealed with (to pick the right key)."""
    return parse(blob)[1]


def decrypt(blob: str, key: bytes, aad: bytes) -> bytes:
    """Open a blob. EnvelopeError for a wrong key, wrong ``aad``, tampering or
    bad format; UnsupportedVersion for a version other than v1."""
    _check_key(key)
    version, key_id, nonce, ciphertext = parse(blob)
    if version != VERSION:
        raise UnsupportedVersion("unsupported envelope version")
    try:
        return AESGCM(bytes(key)).decrypt(nonce, ciphertext, _v1_aad(key_id, aad))
    except InvalidTag:
        raise EnvelopeError("cannot decrypt envelope") from None


# ---------------------------------------------------------------- v2
#
# ``v2:<kek_id>:<dek_nonce>:<wrapped_dek>:<nonce>:<ciphertext>``
#
# Every write draws a fresh 32-byte data key (DEK). The value is sealed under
# the DEK with AAD ``key|version|section``; the DEK is wrapped under the key
# encryption key (KEK) with AAD ``kek_id|key|version``. Re-keying therefore
# touches only the small wrapped DEK. A blob moved to another setting name,
# version, section or KEK id fails to open.


def _value_aad(key: str, version: int, section: str) -> bytes:
    return f"v2|{key}|{version}|{section}".encode("utf-8")


def _wrap_aad(kek_id: str, key: str, version: int) -> bytes:
    return f"v2|{kek_id}|{key}|{version}".encode("utf-8")


def parse_v2(blob: str) -> Tuple[str, str, bytes, bytes, bytes, bytes]:
    """``(version, kek_id, dek_nonce, wrapped_dek, nonce, ciphertext)``."""
    parts = _split(blob)
    if parts[0] != VERSION_2:
        raise EnvelopeError("malformed envelope")
    dek_nonce, wrapped, nonce, ciphertext = _fields(parts, 4)
    if len(dek_nonce) != NONCE_BYTES or len(nonce) != NONCE_BYTES:
        raise EnvelopeError("malformed envelope")
    if len(wrapped) != KEY_BYTES + 16:
        raise EnvelopeError("malformed envelope")
    return parts[0], parts[1], dek_nonce, wrapped, nonce, ciphertext


def _wrap(
    kek: bytes, kek_id: str, dek: bytes, key: str, version: int
) -> Tuple[bytes, bytes]:
    nonce = os.urandom(NONCE_BYTES)
    wrapped = AESGCM(bytes(kek)).encrypt(nonce, dek, _wrap_aad(kek_id, key, version))
    return nonce, wrapped


def _unwrap(
    kek: bytes, kek_id: str, nonce: bytes, wrapped: bytes, key: str, version: int
) -> bytes:
    try:
        return AESGCM(bytes(kek)).decrypt(
            nonce, wrapped, _wrap_aad(kek_id, key, version)
        )
    except InvalidTag:
        raise EnvelopeError("cannot decrypt envelope") from None


def _open_value(
    dek: bytes, nonce: bytes, ciphertext: bytes, key: str, version: int, section: str
) -> bytes:
    try:
        return AESGCM(dek).decrypt(nonce, ciphertext, _value_aad(key, version, section))
    except InvalidTag:
        raise EnvelopeError("cannot decrypt envelope") from None


def _assemble(kek_id: str, fields: Tuple[bytes, ...]) -> str:
    return ":".join([VERSION_2, kek_id] + [_b64e(f) for f in fields])


def encrypt_v2(
    plaintext: bytes, kek: bytes, kek_id: str, key: str, version: int, section: str
) -> str:
    """Seal ``plaintext`` for setting ``key`` at ``version`` in ``section``."""
    _check_key(kek)
    if not _KEY_ID.fullmatch(kek_id):
        raise EnvelopeError("invalid key id")
    dek = os.urandom(KEY_BYTES)
    dek_nonce, wrapped = _wrap(kek, kek_id, dek, key, version)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(
        nonce, plaintext, _value_aad(key, version, section)
    )
    return _assemble(kek_id, (dek_nonce, wrapped, nonce, ciphertext))


def decrypt_v2(blob: str, kek: bytes, key: str, version: int, section: str) -> bytes:
    """Open a v2 blob. EnvelopeError for a wrong KEK, any changed ``key``,
    ``version`` or ``section``, tampering or bad format."""
    _check_key(kek)
    _, kek_id, dek_nonce, wrapped, nonce, ciphertext = parse_v2(blob)
    dek = _unwrap(kek, kek_id, dek_nonce, wrapped, key, version)
    return _open_value(dek, nonce, ciphertext, key, version, section)


def rewrap_v2(
    blob: str,
    old_kek: bytes,
    new_kek: bytes,
    new_kek_id: str,
    key: str,
    version: int,
    section: str,
) -> str:
    """Re-wrap the DEK under a new KEK; the sealed value is carried over
    unchanged (same nonce and ciphertext). The value is opened once to check
    ``section``, so a blob that doesn't belong there is not re-wrapped."""
    _check_key(old_kek)
    _check_key(new_kek)
    if not _KEY_ID.fullmatch(new_kek_id):
        raise EnvelopeError("invalid key id")
    _, kek_id, dek_nonce, wrapped, nonce, ciphertext = parse_v2(blob)
    dek = _unwrap(old_kek, kek_id, dek_nonce, wrapped, key, version)
    _open_value(dek, nonce, ciphertext, key, version, section)
    new_nonce, new_wrapped = _wrap(new_kek, new_kek_id, dek, key, version)
    return _assemble(new_kek_id, (new_nonce, new_wrapped, nonce, ciphertext))
