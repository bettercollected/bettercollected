"""The crypto primitives live in common.settings.crypto; the old module paths
stay importable and point at the same objects."""

from backend.admin.security import envelope, keycheck, keys
from common.settings.crypto import envelope as core_envelope
from common.settings.crypto import keycheck as core_keycheck
from common.settings.crypto import keys as core_keys


def test_envelope_reexports():
    for name in (
        "encrypt", "decrypt", "encrypt_v2", "decrypt_v2", "rewrap_v2", "parse",
        "parse_v2", "key_id_of", "EnvelopeError", "UnsupportedVersion",
    ):
        assert getattr(envelope, name) is getattr(core_envelope, name)


def test_keys_and_keycheck_reexports():
    for name in ("derive_key", "admin_key", "parse_master_key", "MasterKeyError"):
        assert getattr(keys, name) is getattr(core_keys, name)
    for name in ("require_key", "WeakKeyError", "MIN_KEY_BYTES"):
        assert getattr(keycheck, name) is getattr(core_keycheck, name)
