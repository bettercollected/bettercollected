"""Compatibility re-export; the implementation lives in common.settings.crypto."""

from common.settings.crypto.envelope import (  # noqa: F401
    KEY_BYTES,
    NONCE_BYTES,
    VERSION,
    VERSION_2,
    EnvelopeError,
    UnsupportedVersion,
    decrypt,
    decrypt_v2,
    encrypt,
    encrypt_v2,
    key_id_of,
    parse,
    parse_v2,
    rewrap_v2,
)
