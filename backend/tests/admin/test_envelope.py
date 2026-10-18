import os

import pytest

from backend.admin.security import envelope
from backend.admin.security.envelope import EnvelopeError, UnsupportedVersion

KEY = bytes(range(32))
AAD = b"factor-1|ann@example.org"


def test_round_trip_and_format():
    blob = envelope.encrypt(b"JBSWY3DPEHPK3PXP", KEY, "k1", AAD)
    version, key_id, nonce, ciphertext = envelope.parse(blob)
    assert (version, key_id, len(nonce)) == ("v1", "k1", 12)
    assert len(ciphertext) == len(b"JBSWY3DPEHPK3PXP") + 16
    assert blob.count(":") == 3 and "=" not in blob
    assert envelope.key_id_of(blob) == "k1"
    assert envelope.decrypt(blob, KEY, AAD) == b"JBSWY3DPEHPK3PXP"


def test_nonce_is_random_per_call():
    a = envelope.encrypt(b"x", KEY, "k1", AAD)
    b = envelope.encrypt(b"x", KEY, "k1", AAD)
    assert a != b


def test_wrong_key_wrong_aad_and_tampering_fail_with_fixed_message():
    blob = envelope.encrypt(b"top-secret-value", KEY, "k1", AAD)
    other = os.urandom(32)
    head, _, tail = blob.rpartition(":")
    flipped = ("A" if tail[0] != "A" else "B") + tail[1:]
    attempts = [
        lambda: envelope.decrypt(blob, other, AAD),
        lambda: envelope.decrypt(blob, KEY, b"factor-2|ann@example.org"),
        lambda: envelope.decrypt(f"{head}:{flipped}", KEY, AAD),
    ]
    for attempt in attempts:
        with pytest.raises(EnvelopeError) as raised:
            attempt()
        text = str(raised.value)
        assert text == "cannot decrypt envelope"
        assert "top-secret" not in text and blob not in text


def test_future_version_is_reported_not_crashed():
    with pytest.raises(UnsupportedVersion) as raised:
        envelope.decrypt("v2:k1:whatever:whatever:more", KEY, AAD)
    assert "unsupported" in str(raised.value)
    assert issubclass(UnsupportedVersion, EnvelopeError)


@pytest.mark.parametrize(
    "blob",
    [
        "",
        "garbage",
        "v1",
        "v1:k1",
        "v1:k1:AAAA",
        "v1:k1:AAAA:BBBB:CCCC",
        "x1:k1:a:b",
        "v1::AAAAAAAAAAAAAAAA:BBBB",
        "v1:k1:!!!!:BBBB",
        "v1:k1:AAAAAAAAAAAAAAAA:",
        "v1:k1:AAAA:BBBB",
        None,
        5,
        b"v1:k1:a:b",
    ],
)
def test_malformed_blobs_raise_envelope_error(blob):
    with pytest.raises(EnvelopeError):
        envelope.decrypt(blob, KEY, AAD)


@pytest.mark.parametrize("key", [b"", b"short", bytes(31), bytes(33), "k" * 32, None])
def test_bad_keys_are_rejected_without_echoing_them(key):
    with pytest.raises(EnvelopeError) as raised:
        envelope.encrypt(b"x", key, "k1", AAD)
    assert str(raised.value) == "invalid key"
    blob = envelope.encrypt(b"x", KEY, "k1", AAD)
    with pytest.raises(EnvelopeError):
        envelope.decrypt(blob, key, AAD)


@pytest.mark.parametrize("key_id", ["", "a:b", "has space", "x" * 33, "ü"])
def test_bad_key_ids_are_rejected(key_id):
    with pytest.raises(EnvelopeError):
        envelope.encrypt(b"x", KEY, key_id, AAD)


def test_empty_plaintext_round_trips():
    assert envelope.decrypt(envelope.encrypt(b"", KEY, "k", AAD), KEY, AAD) == b""
