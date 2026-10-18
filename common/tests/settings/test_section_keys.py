import base64

import pytest

from common.settings.crypto import envelope
from common.settings.crypto.keys import (
    MasterKeyError,
    derive_from_master,
    derive_key,
    parse_master_key,
)
from common.settings.keys import SectionKeys, SectionNotAllowed

from settings_support import MASTER, MASTER_BYTES, OTHER_MASTER, plain_row, secret_row

WRAP_MAIL_HEX = "10cccab8ad2f9c7c3bdf2b5df18ad5a05a369f090cf2bd6c174811e2dc926f95"


def test_derivation_vector_and_env_path_agree():
    assert derive_from_master(MASTER_BYTES, "settings", "wrap", 1, "mail").hex() == (
        WRAP_MAIL_HEX
    )
    env = {"SETTINGS_MASTER_KEY": MASTER}
    assert derive_key("settings", "wrap", 1, "mail", env=env).hex() == WRAP_MAIL_HEX


@pytest.mark.parametrize("raw", [None, "", "  ", "not base64!!", "a" * 7])
def test_master_key_must_be_present_and_long_enough(raw):
    with pytest.raises(MasterKeyError) as raised:
        parse_master_key(raw)
    if raw and raw.strip():
        assert raw not in str(raised.value)


def test_short_master_keys_are_refused_without_echo():
    short = base64.b64encode(bytes(31)).decode()
    with pytest.raises(MasterKeyError) as raised:
        SectionKeys(short, sections=["mail"])
    assert short not in str(raised.value)
    with pytest.raises(ValueError):
        SectionKeys(bytes(31), sections=["mail"])
    with pytest.raises(ValueError):
        SectionKeys(MASTER, sections=["bad section!"])
    with pytest.raises(MasterKeyError):
        SectionKeys(MASTER, sections=["mail"], master_previous="short")


def test_only_requested_sections_are_derivable():
    keys = SectionKeys(MASTER, sections=["mail"])
    assert keys.wrap_key("mail") == derive_from_master(
        MASTER_BYTES, "settings", "wrap", 1, "mail"
    )
    assert keys.signing_key() == derive_from_master(MASTER_BYTES, "settings", "sign")
    for call in (
        lambda: keys.wrap_key("ai"),
        lambda: keys.seal("ai", "AI_X", 1, "v"),
        lambda: keys.open("ai", "AI_X", 1, "v2:x"),
        lambda: keys.rewrap("ai", "AI_X", 1, "v2:x"),
        lambda: keys.wrap_key(None),
    ):
        with pytest.raises(SectionNotAllowed):
            call()


def test_the_master_key_is_not_kept():
    keys = SectionKeys(MASTER, sections=["mail"])
    held = [v for v in vars(keys).values()]
    flat = repr(held).encode() + repr(keys).encode()
    assert MASTER_BYTES not in flat and MASTER.encode() not in flat
    assert all(MASTER_BYTES != v for v in held if isinstance(v, bytes))


def test_seal_and_open_round_trip_bound_to_the_row(keys):
    blob = keys.seal("mail", "MAIL_PASSWORD", 2, "hunter2-value")
    assert "hunter2" not in blob and blob.startswith("v2:w1-")
    assert keys.open("mail", "MAIL_PASSWORD", 2, blob) == "hunter2-value"
    for args in (("MAIL_USER", 2), ("MAIL_PASSWORD", 3)):
        with pytest.raises(envelope.EnvelopeError):
            keys.open("mail", args[0], args[1], blob)
    with pytest.raises(envelope.EnvelopeError):  # moved to another section
        keys.open("ai", "MAIL_PASSWORD", 2, blob)
    with pytest.raises(envelope.EnvelopeError):
        SectionKeys(OTHER_MASTER, sections=["mail"]).open(
            "mail", "MAIL_PASSWORD", 2, blob
        )


def test_signatures_follow_the_current_key(keys):
    row = keys.sign_row(plain_row())
    assert keys.verify_row(row)
    assert not SectionKeys(OTHER_MASTER, sections=[]).verify_row(row)
    manifest = keys.sign_manifest(4, [row])
    assert keys.verify_manifest(manifest)
    assert not SectionKeys(OTHER_MASTER, sections=[]).verify_manifest(manifest)


def test_rotation_window_with_master_previous():
    old = SectionKeys(MASTER, sections=["mail"])
    blob = secret_row(old).blob
    row = old.sign_row(plain_row())
    manifest = old.sign_manifest(1, [row])

    during = SectionKeys(OTHER_MASTER, sections=["mail"], master_previous=MASTER)
    assert during.rotating and not old.rotating
    # decrypt and verify with the previous key ...
    assert during.open("mail", "MAIL_PASSWORD", 1, blob) == "smtp-pass-1"
    assert during.verify_row(row) and during.verify_manifest(manifest)
    assert during.needs_rewrap("mail", blob)
    # ... but always sign and seal with the current one
    new_row = during.sign_row(plain_row(version=4))
    assert not old.verify_row(new_row)
    new_blob = during.seal("mail", "MAIL_PASSWORD", 5, "next")
    with pytest.raises(envelope.EnvelopeError):
        old.open("mail", "MAIL_PASSWORD", 5, new_blob)
    assert not during.needs_rewrap("mail", new_blob)

    # rewrap moves old blobs to the current key; then the previous can go
    moved = during.rewrap("mail", "MAIL_PASSWORD", 1, blob)
    assert not during.needs_rewrap("mail", moved)
    after = SectionKeys(OTHER_MASTER, sections=["mail"])
    assert after.open("mail", "MAIL_PASSWORD", 1, moved) == "smtp-pass-1"
    assert not after.verify_row(row)  # old signatures need re-signing first


def test_same_previous_as_current_is_not_a_rotation():
    assert not SectionKeys(MASTER, sections=[], master_previous=MASTER).rotating


def test_fingerprint_is_stable_and_not_the_key(keys):
    assert keys.fingerprint == SectionKeys(MASTER, sections=[]).fingerprint
    assert keys.fingerprint != SectionKeys(OTHER_MASTER, sections=[]).fingerprint
    assert len(keys.fingerprint) == 12
    assert keys.fingerprint != MASTER_BYTES.hex()[:12]
