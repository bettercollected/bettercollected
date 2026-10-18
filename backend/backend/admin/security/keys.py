"""Compatibility re-export; the implementation lives in common.settings.crypto."""

from common.settings.crypto.keys import (  # noqa: F401
    KEY_BYTES,
    MASTER_KEY_KEY,
    MasterKeyError,
    admin_key,
    derive_key,
    parse_master_key,
)
