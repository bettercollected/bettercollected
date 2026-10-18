"""AES_HEX_KEY (the stack's AUTH_AES_HEX_KEY) must be set, a Fernet key and
not a value published in the repository, or the executor does not start."""

import base64
import hashlib

import pytest

import settings.shipped_secrets as shipped
from settings.application import ApplicationSettings, require_aes_hex_key
from settings.shipped_secrets import InsecureSecretError

GOOD_FERNET = base64.urlsafe_b64encode(b"e" * 32).decode()
# Stands in for a published value: the real ones are only known by their hash.
PUBLISHED = base64.urlsafe_b64encode(b"p" * 32).decode()


def configured(monkeypatch, value):
    monkeypatch.setenv("AES_HEX_KEY", value)
    return ApplicationSettings(_env_file=None)


def test_own_key_passes(monkeypatch):
    require_aes_hex_key(configured(monkeypatch, GOOD_FERNET))


@pytest.mark.parametrize(
    "value, problem",
    [
        ("", "AES_HEX_KEY is not set"),
        ("not-a-key", "AES_HEX_KEY is not a Fernet key"),
        (PUBLISHED, "AES_HEX_KEY is a value that was published"),
    ],
)
def test_refused(monkeypatch, value, problem):
    monkeypatch.setattr(
        shipped,
        "SHIPPED_SECRET_SHA256",
        shipped.SHIPPED_SECRET_SHA256
        | {hashlib.sha256(PUBLISHED.encode()).hexdigest()},
    )
    with pytest.raises(InsecureSecretError) as error:
        require_aes_hex_key(configured(monkeypatch, value))
    assert "Refusing to start the actions-executor" in str(error.value)
    assert problem in str(error.value)
    assert PUBLISHED not in str(error.value)
