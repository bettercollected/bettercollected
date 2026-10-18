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
from typing import Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = "v1"
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


def encrypt(plaintext: bytes, key: bytes, key_id: str, aad: bytes) -> str:
    """Seal ``plaintext`` under ``key`` (32 bytes), bound to ``aad``."""
    _check_key(key)
    if not _KEY_ID.fullmatch(key_id):
        raise EnvelopeError("invalid key id")
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(bytes(key)).encrypt(nonce, plaintext, aad)
    return f"{VERSION}:{key_id}:{_b64e(nonce)}:{_b64e(ciphertext)}"


def parse(blob: str) -> Tuple[str, str, bytes, bytes]:
    """``(version, key_id, nonce, ciphertext)`` of a blob.

    Raises UnsupportedVersion for a well-formed version other than v1 (a
    newer blob is reported, not mistaken for corruption) and EnvelopeError
    for anything else."""
    if not isinstance(blob, str):
        raise EnvelopeError("malformed envelope")
    parts = blob.split(":")
    if not re.fullmatch(r"v[0-9]{1,3}", parts[0]):
        raise EnvelopeError("malformed envelope")
    if parts[0] != VERSION:
        raise UnsupportedVersion("unsupported envelope version")
    if len(parts) != 4 or not _KEY_ID.fullmatch(parts[1]):
        raise EnvelopeError("malformed envelope")
    nonce = _b64d(parts[2])
    if len(nonce) != NONCE_BYTES:
        raise EnvelopeError("malformed envelope")
    return parts[0], parts[1], nonce, _b64d(parts[3])


def key_id_of(blob: str) -> str:
    """The key id a blob was sealed with (to pick the right key)."""
    return parse(blob)[1]


def decrypt(blob: str, key: bytes, aad: bytes) -> bytes:
    """Open a blob. EnvelopeError for a wrong key, wrong ``aad``, tampering or
    bad format; UnsupportedVersion for a version other than v1."""
    _check_key(key)
    _, _, nonce, ciphertext = parse(blob)
    try:
        return AESGCM(bytes(key)).decrypt(nonce, ciphertext, aad)
    except InvalidTag:
        raise EnvelopeError("cannot decrypt envelope") from None
