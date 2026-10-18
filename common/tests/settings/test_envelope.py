import os

import pytest

from common.settings.crypto import envelope
from common.settings.crypto.envelope import EnvelopeError, UnsupportedVersion

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
        envelope.decrypt("v3:k1:whatever:whatever:more", KEY, AAD)
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


# ---------------------------------------------------------------- v2

KEK = bytes(range(100, 132))
ARGS = ("smtp.password", 3, "admin_mail")


def sealed(plain=b"hunter2-value"):
    return envelope.encrypt_v2(plain, KEK, "kek1", *ARGS)


def test_v2_round_trip_format_and_fresh_dek_per_write():
    a, b = sealed(), sealed()
    assert a != b
    assert a.startswith("v2:kek1:") and a.count(":") == 5 and "=" not in a
    assert envelope.decrypt_v2(a, KEK, *ARGS) == b"hunter2-value"
    version, kek_id, dek_nonce, wrapped, nonce, ciphertext = envelope.parse_v2(a)
    assert (version, kek_id) == ("v2", "kek1")
    assert (len(dek_nonce), len(wrapped), len(nonce)) == (12, 48, 12)
    assert len(ciphertext) == len(b"hunter2-value") + 16
    assert envelope.parse(a)[:2] == ("v2", "kek1")
    assert envelope.key_id_of(a) == "kek1"
    assert envelope.parse_v2(a)[3] != envelope.parse_v2(b)[3]


def test_v2_with_fixed_randomness_is_a_pure_function_of_its_inputs(monkeypatch):
    monkeypatch.setattr(
        envelope.os,
        "urandom",
        lambda n: b"\x07" * n,
    )
    first = envelope.encrypt_v2(b"value", KEK, "kek1", *ARGS)
    second = envelope.encrypt_v2(b"value", KEK, "kek1", *ARGS)
    monkeypatch.undo()
    assert first == second
    assert envelope.parse_v2(first)[2] == b"\x07" * 12
    assert envelope.decrypt_v2(first, KEK, *ARGS) == b"value"
    assert (
        envelope.decrypt_v2(envelope.encrypt_v2(b"", KEK, "k", *ARGS), KEK, *ARGS)
        == b""
    )


def test_v2_wrong_kek_and_swapped_bindings_fail_with_fixed_message():
    blob = sealed()
    cases = [
        (KEK, ("other.key", 3, "admin_mail")),
        (KEK, ("smtp.password", 4, "admin_mail")),
        (KEK, ("smtp.password", 3, "other_section")),
        (os.urandom(32), ARGS),
    ]
    for kek, args in cases:
        with pytest.raises(EnvelopeError) as raised:
            envelope.decrypt_v2(blob, kek, *args)
        assert str(raised.value) == "cannot decrypt envelope"
        assert "hunter2" not in str(raised.value)


def test_v2_changed_kek_id_fails():
    forged = sealed().replace("v2:kek1:", "v2:kek2:", 1)
    with pytest.raises(EnvelopeError):
        envelope.decrypt_v2(forged, KEK, *ARGS)


def test_v2_tampering_each_field_fails():
    parts = sealed().split(":")
    for index in (2, 3, 4, 5):
        field = parts[index]
        flipped = ("A" if field[0] != "A" else "B") + field[1:]
        blob = ":".join(parts[:index] + [flipped] + parts[index + 1 :])
        with pytest.raises(EnvelopeError):
            envelope.decrypt_v2(blob, KEK, *ARGS)


def test_v2_truncated_and_malformed_blobs():
    blob = sealed()
    parts = blob.split(":")
    candidates = [":".join(parts[:n]) for n in range(1, 6)]
    candidates += [
        blob + ":extra",
        blob[:-6],
        "v2",
        "v2::a:b:c:d",
        "v2:kek1:!!:!!:!!:!!",
    ]
    candidates += ["", None, ":".join(parts[:3] + [parts[3][:-4]] + parts[4:])]
    for candidate in candidates:
        with pytest.raises(EnvelopeError):
            envelope.decrypt_v2(candidate, KEK, *ARGS)


def test_v1_and_v2_do_not_open_each_other():
    v1 = envelope.encrypt(b"x", KEY, "k1", AAD)
    with pytest.raises(EnvelopeError):
        envelope.decrypt_v2(v1, KEK, *ARGS)
    with pytest.raises(UnsupportedVersion):
        envelope.decrypt(sealed(), KEK, AAD)
    assert envelope.parse(v1)[0] == "v1"


def test_v2_bad_keys_and_ids():
    with pytest.raises(EnvelopeError):
        envelope.encrypt_v2(b"x", b"short", "k", *ARGS)
    with pytest.raises(EnvelopeError):
        envelope.encrypt_v2(b"x", KEK, "bad id", *ARGS)
    with pytest.raises(EnvelopeError):
        envelope.decrypt_v2(sealed(), b"short", *ARGS)


def test_rewrap_changes_only_the_wrapped_dek():
    blob = sealed(b"payload")
    new_kek = os.urandom(32)
    moved = envelope.rewrap_v2(blob, KEK, new_kek, "kek2", *ARGS)
    old, new = envelope.parse_v2(blob), envelope.parse_v2(moved)
    assert new[1] == "kek2" and new[4:] == old[4:]  # same value nonce + ciphertext
    assert new[2:4] != old[2:4]
    assert envelope.decrypt_v2(moved, new_kek, *ARGS) == b"payload"
    with pytest.raises(EnvelopeError):
        envelope.decrypt_v2(moved, KEK, *ARGS)
    assert envelope.decrypt_v2(blob, KEK, *ARGS) == b"payload"


def test_rewrap_refuses_wrong_old_kek_or_binding():
    blob = sealed()
    new_kek = os.urandom(32)
    cases = [
        (os.urandom(32), ARGS),
        (KEK, ("x", 3, "admin_mail")),
        (KEK, ("smtp.password", 3, "x")),
    ]
    for old, args in cases:
        with pytest.raises(EnvelopeError):
            envelope.rewrap_v2(blob, old, new_kek, "kek2", *args)
    with pytest.raises(EnvelopeError):
        envelope.rewrap_v2(blob, KEK, b"short", "kek2", *ARGS)
    with pytest.raises(EnvelopeError):
        envelope.rewrap_v2(blob, KEK, new_kek, "bad id", *ARGS)


# ------------------------------------------------- AAD binding and vectors


def test_v1_key_id_is_bound_into_the_aead():
    blob = envelope.encrypt(b"secret", KEY, "k1", AAD)
    forged = blob.replace("v1:k1:", "v1:k2:", 1)
    with pytest.raises(EnvelopeError) as raised:
        envelope.decrypt(forged, KEY, AAD)
    assert str(raised.value) == "cannot decrypt envelope"
    assert envelope.decrypt(blob, KEY, AAD) == b"secret"


def test_v1_frozen_vector(monkeypatch):
    """Freezes the AAD construction (``v1|<key_id>|<aad>``) and the format."""
    monkeypatch.setattr(envelope.os, "urandom", lambda n: bytes(range(n)))
    blob = envelope.encrypt(b"JBSWY3DPEHPK3PXP", KEY, "k1", AAD)
    monkeypatch.undo()
    assert blob == V1_VECTOR
    assert envelope.decrypt(V1_VECTOR, KEY, AAD) == b"JBSWY3DPEHPK3PXP"


def test_v2_frozen_vector(monkeypatch):
    """Freezes the v2 format and both AADs."""
    monkeypatch.setattr(envelope.os, "urandom", lambda n: bytes(range(n)))
    blob = envelope.encrypt_v2(b"value", KEK, "kek1", *ARGS)
    monkeypatch.undo()
    assert blob == V2_VECTOR
    assert envelope.decrypt_v2(V2_VECTOR, KEK, *ARGS) == b"value"


V1_VECTOR = "v1:k1:AAECAwQFBgcICQoL:DUCFTJzWhkvICcfAgrkgPa3SMTnXhHWbprTR1Qd1LY4"
V2_VECTOR = (
    "v2:kek1:AAECAwQFBgcICQoL:n6o6T7lIx-6VGpTDmpeGvfkGL4M5FsYy3wvzEE_xX_8Nus2syqyoF2lOiCooECHE"
    ":AAECAwQFBgcICQoL:MWO6bqCQSQQSdfEXUkF0cA55NR7t"
)
