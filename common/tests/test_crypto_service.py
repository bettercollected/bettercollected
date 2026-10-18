"""CryptoService: a plaintext starting with the ciphertext prefix ("v1:") is
still encrypted, and a prefixed value that does not decrypt raises a typed
error that never carries the value."""

import base64
import io

import common.services  # noqa: F401  (resolve the package at collection)
import pytest
import tink
from tink import aead, cleartext_keyset_handle

WS, FORM = "65e5501d00000000000000a1", "form-1"


@pytest.fixture(scope="module")
def keyset() -> str:
    aead.register()
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    stream = io.StringIO()
    cleartext_keyset_handle.write(tink.JsonKeysetWriter(stream), handle)
    return base64.b64encode(stream.getvalue().encode("ascii")).decode("ascii")


@pytest.fixture
def crypto(keyset, monkeypatch):
    # the module builds its default instance from the environment on import
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", keyset)
    from common.services.crypto_service import CryptoService

    return CryptoService(keyset)


@pytest.fixture
def unreadable():
    from common.services.crypto_service import UnreadableCiphertext

    return UnreadableCiphertext


@pytest.mark.parametrize(
    "plaintext", ["v1:hello", b"v1:hello", "v1:", '"v1:a raw string answer"']
)
def test_a_prefixed_plaintext_is_encrypted_and_round_trips(crypto, plaintext):
    stored = crypto.encrypt(WS, FORM, plaintext)
    expected = plaintext if isinstance(plaintext, bytes) else plaintext.encode()

    assert stored.startswith(b"v1:") and stored != expected
    assert expected[len(b"v1:") :] not in stored or expected == b"v1:"
    assert crypto.decrypt(WS, FORM, stored) == expected


def test_encrypt_always_encrypts(crypto):
    """Encrypting a ciphertext wraps it again: callers holding ciphertext
    must store it as is, never pass it to encrypt."""
    once = crypto.encrypt(WS, FORM, '{"q1": "a"}')
    twice = crypto.encrypt(WS, FORM, once)

    assert twice != once
    assert crypto.decrypt(WS, FORM, twice) == once
    assert crypto.decrypt(WS, FORM, once) == b'{"q1": "a"}'


def test_a_stored_prefixed_plaintext_fails_to_decrypt_without_the_value(
    crypto, unreadable
):
    # what encrypt used to store for "v1:hello": the plaintext itself
    with pytest.raises(unreadable) as raised:
        crypto.decrypt(WS, FORM, b"v1:hello")
    assert "hello" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert isinstance(raised.value, ValueError)


def test_corrupted_or_misplaced_ciphertext_fails_to_decrypt(crypto, unreadable):
    stored = crypto.encrypt(WS, FORM, "secret")
    corrupted = stored[:-1] + bytes([stored[-1] ^ 1])

    with pytest.raises(unreadable):
        crypto.decrypt(WS, FORM, corrupted)
    with pytest.raises(unreadable):
        crypto.decrypt(WS, "another-form", stored)  # another context
    with pytest.raises(unreadable):
        crypto.decrypt(WS, FORM, b"v1:")


def test_values_without_the_prefix_pass_through_decrypt(crypto):
    assert crypto.decrypt(WS, FORM, b'{"q1": "a"}') == b'{"q1": "a"}'
    assert crypto.decrypt(WS, FORM, "v1:text") == "v1:text"  # str: never ciphertext
