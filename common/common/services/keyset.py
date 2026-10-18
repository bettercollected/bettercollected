"""The Tink AEAD keyset stored responses are encrypted with, and its rotation.

``MASTER_ENCRYPTION_KEYSET`` is a Tink keyset (JSON, base64-encoded). Values
are stored as ``v1:`` + a Tink ciphertext, and a Tink ciphertext starts with
the id of the key that made it (output prefix ``TINK``: one byte 0x01 and the
key id as 4 bytes big-endian), so it is known which key every stored value
needs without decrypting it. Rotation (backend/scripts/rotate_response_keyset.py,
docs/response-keyset-rotation.md) adds a key as the new primary, re-encrypts
everything under it and then drops the keys nothing uses any more.

Earlier versions of this repository published a keyset (deployment env files,
a README, CI). A stack still using one of its keys has its responses readable
by anyone, but it cannot simply switch keysets the way it can switch the JWT
secret: a new keyset cannot read what the old one encrypted. So such a keyset
is not refused at startup but warned about, and the key material is compared
by SHA-256 digest only.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import logging
from typing import Iterable, List, Optional, Union

import tink
from tink import aead, cleartext_keyset_handle
from tink.proto import aes_gcm_pb2, tink_pb2

from common.configs.shipped_secrets import normalize_secret

logger = logging.getLogger(__name__)

KEYSET_ENV = "MASTER_ENCRYPTION_KEYSET"
ROTATION_DOC = "docs/response-keyset-rotation.md"
CIPHERTEXT_PREFIX = b"v1:"
AES_GCM_TYPE_URL = "type.googleapis.com/google.crypto.tink.AesGcmKey"

# SHA-256 of the raw AES key bytes of every key published in this
# repository's history (all of it, every branch: one keyset, one key), never
# the keys themselves.
PUBLISHED_KEY_SHA256 = frozenset(
    {
        "ac1c933c41e07da37aed80273eef7cda0e99d383791a6435b850dcfda7f4f8cb",
    }
)


class KeysetError(ValueError):
    """The value is not a usable Tink keyset."""


# ------------------------------------------------------------------ keysets
def parse_keyset(value: Union[str, bytes, None]) -> tink_pb2.Keyset:
    """The keyset in ``value``: base64 of the JSON keyset (the env format), or
    the JSON itself. The error never quotes the value."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = normalize_secret(value)
    if not text:
        raise KeysetError("the keyset is empty")
    if not text.lstrip().startswith("{"):
        try:
            text = base64.b64decode(text, validate=False).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            raise KeysetError("the keyset is neither base64 nor JSON") from None
    try:
        keyset = tink.JsonKeysetReader(text).read()
    except Exception:  # tink / protobuf parse errors quote their input
        raise KeysetError("the keyset is not a Tink JSON keyset") from None
    if not keyset.key:
        raise KeysetError("the keyset has no keys")
    if keyset.primary_key_id not in {key.key_id for key in keyset.key}:
        raise KeysetError("the keyset's primary key is not one of its keys")
    return keyset


def encode_keyset(keyset: tink_pb2.Keyset) -> str:
    """The env format: the JSON keyset, base64-encoded."""
    buffer = io.StringIO()
    tink.JsonKeysetWriter(buffer).write(keyset)
    return base64.b64encode(buffer.getvalue().encode("utf-8")).decode("ascii")


def key_material(key: tink_pb2.Keyset.Key) -> bytes:
    """The secret bytes of one key: the raw AES key of an AES-GCM key, the
    serialized key proto for any other type."""
    raw = key.key_data.value
    if key.key_data.type_url == AES_GCM_TYPE_URL:
        parsed = aes_gcm_pb2.AesGcmKey()
        parsed.ParseFromString(raw)
        return parsed.key_value
    return raw


def key_digest(key: tink_pb2.Keyset.Key) -> str:
    return hashlib.sha256(key_material(key)).hexdigest()


def published_key_ids(
    keyset: tink_pb2.Keyset, denylist: Optional[Iterable[str]] = None
) -> List[int]:
    """Ids of the keys in ``keyset`` whose material was published."""
    denied = frozenset(PUBLISHED_KEY_SHA256 if denylist is None else denylist)
    return [key.key_id for key in keyset.key if key_digest(key) in denied]


def published_key_warning(
    value: Optional[str],
    name: str = KEYSET_ENV,
    denylist: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """What to warn about a keyset holding a published key, naming only the
    variable; None when it holds none (or is not a keyset at all, which
    loading it reports on its own)."""
    try:
        keyset = parse_keyset(value)
    except KeysetError:
        return None
    published = published_key_ids(keyset, denylist)
    if not published:
        return None
    if keyset.primary_key_id in published:
        return (
            f"{name} is a keyset that was published in the bettercollected "
            "repository, and responses are encrypted with it: anyone with a "
            "copy of the repository and of the data can read them. Rotate it "
            f"(add a key, re-encrypt, drop the old one): see {ROTATION_DOC}."
        )
    return (
        f"{name} still holds a key that was published in the bettercollected "
        "repository (no longer the primary): data it encrypted stays readable "
        "by anyone with a copy of the repository until it is re-encrypted and "
        f"the key dropped: see {ROTATION_DOC}."
    )


def warn_if_published(
    value: Optional[str],
    name: str = KEYSET_ENV,
    denylist: Optional[Iterable[str]] = None,
) -> bool:
    """Log a WARNING when the keyset holds a published key; True if it does."""
    message = published_key_warning(value, name, denylist)
    if message:
        logger.warning(message)
    return message is not None


# --------------------------------------------------------------- rotation
def _new_aes256_gcm_key() -> tink_pb2.Keyset.Key:
    """One fresh key from Tink's AES256_GCM template (TINK output prefix)."""
    aead.register()
    generated = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    buffer = io.StringIO()
    cleartext_keyset_handle.write(tink.JsonKeysetWriter(buffer), generated)
    return tink.JsonKeysetReader(buffer.getvalue()).read().key[0]


def add_primary_key(keyset: tink_pb2.Keyset) -> tink_pb2.Keyset:
    """A copy of ``keyset`` with a new AES-256-GCM key as its primary; the
    existing keys stay (enabled) so what they encrypted still decrypts."""
    taken = {key.key_id for key in keyset.key}
    new_key = _new_aes256_gcm_key()
    while new_key.key_id in taken:  # 1 in 2^31 per existing key; re-roll
        new_key = _new_aes256_gcm_key()
    rotated = tink_pb2.Keyset()
    rotated.CopyFrom(keyset)
    rotated.key.append(new_key)
    rotated.primary_key_id = new_key.key_id
    return rotated


def add_secondary_key(keyset: tink_pb2.Keyset) -> tink_pb2.Keyset:
    """A copy of ``keyset`` with a new AES-256-GCM key added as a SECONDARY: the
    primary stays, so a service given this keyset keeps encrypting with the old
    key and can already decrypt with the new one. The first half of a
    two-step rotation: add as secondary, wait until every service holds it,
    then :func:`promote`. The new key's id is the one id not in ``keyset``."""
    rotated = add_primary_key(keyset)
    rotated.primary_key_id = keyset.primary_key_id
    return rotated


def promote(keyset: tink_pb2.Keyset, key_id: int) -> tink_pb2.Keyset:
    """A copy of ``keyset`` whose primary is ``key_id``, which must already be
    one of its enabled keys. Promoting the current primary changes nothing."""
    chosen = [k for k in keyset.key if k.key_id == key_id]
    if not chosen:
        raise KeysetError("the key to promote is not in the keyset")
    if chosen[0].status != tink_pb2.ENABLED:
        raise KeysetError("the key to promote is not enabled")
    promoted = tink_pb2.Keyset()
    promoted.CopyFrom(keyset)
    promoted.primary_key_id = key_id
    return promoted


def key_ids(keyset: tink_pb2.Keyset) -> List[int]:
    return [key.key_id for key in keyset.key]


def only_primary(keyset: tink_pb2.Keyset) -> tink_pb2.Keyset:
    """A copy of ``keyset`` holding its primary key only."""
    primary = tink_pb2.Keyset(primary_key_id=keyset.primary_key_id)
    primary.key.extend(k for k in keyset.key if k.key_id == keyset.primary_key_id)
    return primary


def ciphertext_key_id(data) -> Optional[int]:
    """The id of the key a stored value was encrypted with; None when the value
    is not a ``v1:`` ciphertext or names no key (a RAW-prefix key)."""
    if not isinstance(data, (bytes, bytearray)):
        return None
    data = bytes(data)
    if not data.startswith(CIPHERTEXT_PREFIX):
        return None
    body = data[len(CIPHERTEXT_PREFIX) :]
    # 0x01 TINK, 0x00 LEGACY/CRUNCHY: both carry the key id
    if len(body) < 5 or body[0] not in (0x00, 0x01):
        return None
    return int.from_bytes(body[1:5], "big")


def is_ciphertext(data) -> bool:
    return isinstance(data, (bytes, bytearray)) and bytes(data).startswith(
        CIPHERTEXT_PREFIX
    )


def describe_keyset(keyset: tink_pb2.Keyset) -> dict:
    """Ids and status only: safe to print."""
    return {
        "primary_key_id": keyset.primary_key_id,
        "key_ids": [key.key_id for key in keyset.key],
        "published_key_ids": published_key_ids(keyset),
    }


# --------------------------------------------------------------- the cipher
class UnreadableCiphertext(ValueError):
    """A stored value carries the ciphertext prefix but does not decrypt:
    corrupted, encrypted under another key or context, or plaintext that
    happened to start with the prefix (stored before ``encrypt`` stopped
    passing such values through). The message never includes the value."""


class CryptoService:
    """Encrypts and decrypts stored values with the keyset, bound to the
    workspace and form (``workspace_id|form_id|`` + context is the AEAD's
    associated data)."""

    def __init__(self, keyset: str):
        super(CryptoService, self).__init__()
        self.version = "v1"
        self.ciphertext_prefix: bytes = bytes(self.version + ":", "utf-8")
        self.crypto = self.setup_crypto(keyset)
        self.keyset = parse_keyset(keyset)
        self.primary_key_id: int = self.keyset.primary_key_id

    def setup_crypto(self, keyset: str):
        aead.register()
        decoded_keyset = base64.b64decode(keyset).decode("ascii")
        keyset_handle = cleartext_keyset_handle.read(
            tink.JsonKeysetReader(decoded_keyset)
        )
        return keyset_handle.primitive(aead.Aead)

    @property
    def published_key_in_keyset(self) -> bool:
        """Whether a key published in the repository is in this keyset."""
        return bool(published_key_ids(self.keyset))

    def encrypt(
        self,
        workspace_id: str,
        form_id: str,
        data: Union[bytes, str],
        context: bytes = b"",
    ):
        # Always encrypts: a plaintext that starts with the prefix ("v1:...")
        # is still plaintext. Callers holding ciphertext must not call this.
        data = bytes(data, "utf-8") if isinstance(data, str) else data
        full_context = self.compose_full_context(workspace_id, form_id, context)
        ciphertext = self.crypto.encrypt(data, full_context)
        return self.ciphertext_prefix + ciphertext

    def decrypt(
        self, workspace_id: str, form_id: str, data: bytes, context: bytes = b""
    ):
        if isinstance(data, str) or not data.startswith(self.ciphertext_prefix):
            return data
        ciphertext = data[len(self.ciphertext_prefix) :]
        full_context = self.compose_full_context(workspace_id, form_id, context)
        try:
            return self.crypto.decrypt(ciphertext, full_context)
        except tink.TinkError:
            raise UnreadableCiphertext("stored value could not be decrypted") from None

    def compose_full_context(self, workspace_id: str, form_id: str, context: bytes):
        return bytes(f"{workspace_id}|{form_id}|", "utf-8") + context
