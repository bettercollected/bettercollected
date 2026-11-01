"""The executor's Fernet cipher under a key ring (docs/auth-key-rotation.md):
``AES_HEX_KEY`` is ``<current>[,<previous>]``, as the stack's AUTH_AES_HEX_KEY
is during a rotation. Throwaway keys only."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from settings.application import ApplicationSettings, require_aes_hex_key

OLD = Fernet.generate_key().decode()
NEW = Fernet.generate_key().decode()


@pytest.fixture
def crypto_class(monkeypatch):
    monkeypatch.setenv("AES_HEX_KEY", OLD)
    from configs.crypto import Crypto

    return Crypto


def test_a_single_key_is_unchanged(crypto_class):
    sealed = crypto_class(OLD).encrypt("secret value")
    assert Fernet(OLD).decrypt(sealed.encode()) == b"secret value"
    assert crypto_class(OLD).decrypt(sealed) == "secret value"


def test_a_ring_seals_with_the_first_and_opens_with_either(crypto_class):
    old_sealed = crypto_class(OLD).encrypt("sealed under the old key")
    ring = crypto_class(f"{NEW},{OLD}")
    assert ring.decrypt(old_sealed) == "sealed under the old key"
    fresh = ring.encrypt("sealed under the new key")
    assert crypto_class(NEW).decrypt(fresh) == "sealed under the new key"
    with pytest.raises(InvalidToken):
        crypto_class(OLD).decrypt(fresh)
    with pytest.raises(InvalidToken):
        crypto_class(NEW).decrypt(old_sealed)


def test_the_start_check_accepts_a_ring_and_refuses_a_bad_member(monkeypatch):
    monkeypatch.setenv("AES_HEX_KEY", f"{NEW},{OLD}")
    require_aes_hex_key(ApplicationSettings(_env_file=None))
    monkeypatch.setenv("AES_HEX_KEY", f"{NEW},not-a-key")
    with pytest.raises(Exception) as error:
        require_aes_hex_key(ApplicationSettings(_env_file=None))
    assert "AES_HEX_KEY is not a Fernet key" in str(error.value)
    assert NEW not in str(error.value)


def test_the_ring_warning_names_the_setting_and_never_a_key(monkeypatch, caplog):
    import logging

    from settings import shipped_secrets

    caplog.set_level(logging.WARNING, logger="common.shipped_secrets")
    shipped_secrets.require_secrets(
        "the executor", fernet_keys={"AES_HEX_KEY": f"{NEW},{OLD}"}
    )
    assert [r.getMessage() for r in caplog.records] == [
        "AES_HEX_KEY is read as a key ring of two: the first encrypts, both decrypt (a rotation under way)"
    ]
    assert OLD not in caplog.text and NEW not in caplog.text
