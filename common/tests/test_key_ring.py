"""Key rings: ``AUTH_JWT_SECRET`` and ``AUTH_AES_HEX_KEY`` hold ``<current>[,<previous>]``.

Throwaway keys only. The first member signs and encrypts; every member
verifies and decrypts; a single key is a ring of one and behaves as before.
"""

import secrets
import time

import pytest
from cryptography.fernet import Fernet, InvalidToken

from common.configs import shipped_secrets
from common.configs.crypto import Crypto
from common.settings import key_ring, secret_checks

OLD_F = Fernet.generate_key().decode()
NEW_F = Fernet.generate_key().decode()
THIRD_F = Fernet.generate_key().decode()
OLD_J = secrets.token_hex(32)
NEW_J = secrets.token_hex(32)


# ------------------------------------------------------------------ parsing
@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        ("   ", []),
        (OLD_F, [OLD_F]),
        (f"{NEW_F},{OLD_F}", [NEW_F, OLD_F]),
        (f" {NEW_F} , {OLD_F} ", [NEW_F, OLD_F]),
    ],
)
def test_fernet_members(value, expected):
    assert key_ring.fernet_members(value) == expected
    assert shipped_secrets.fernet_members(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        (OLD_J, [OLD_J]),
        (f"{NEW_J},{OLD_J}", [NEW_J, OLD_J]),
        # a hand-made single secret that contains a comma is still one secret
        ("short,secret-with-a-comma-but-not-a-ring-0123456789", ["short,secret-with-a-comma-but-not-a-ring-0123456789"]),
        (f"{OLD_J},{NEW_J},{OLD_J}", [f"{OLD_J},{NEW_J},{OLD_J}"]),  # three parts: not a ring
        (f"{NEW_J}, {OLD_J}", [f"{NEW_J}, {OLD_J}"]),  # whitespace inside: not a ring
    ],
)
def test_token_members_rule(value, expected):
    assert key_ring.token_members(value) == expected
    # the copy the workers carry applies the very same rule
    assert shipped_secrets.token_members(value) == expected


def test_primary_and_join():
    assert key_ring.primary([NEW_J, OLD_J]) == NEW_J
    assert key_ring.primary([]) == ""
    assert key_ring.join([NEW_J, OLD_J]) == f"{NEW_J},{OLD_J}"


def test_derived_keys_differ_per_member_and_label():
    keys = key_ring.derive_all([NEW_J, OLD_J], b"label-a")
    assert len(keys) == 2 and keys[0] != keys[1]
    assert key_ring.derive(NEW_J, b"label-a") == keys[0]
    assert key_ring.derive(NEW_J, b"label-b") != keys[0]


# ------------------------------------------------------------------- checks
def test_ring_formats_accept_one_or_two_distinct_good_keys():
    assert secret_checks.check_fernet_ring(OLD_F) is None
    assert secret_checks.check_fernet_ring(f"{NEW_F},{OLD_F}") is None
    assert secret_checks.check_token_ring(OLD_J) is None
    assert secret_checks.check_token_ring(f"{NEW_J},{OLD_J}") is None
    for bad in (f"{OLD_F},{OLD_F}", f"{NEW_F},{OLD_F},{THIRD_F}", f"{OLD_F},nope", "", ","):
        assert secret_checks.check_fernet_ring(bad)[0] in ("bad_ring", "not_fernet"), bad
    for bad in (f"{OLD_J},{OLD_J}", "", "short"):
        assert secret_checks.check_token_ring(bad) is not None, bad
    assert {"token_ring", "fernet_ring"} <= secret_checks.SECRET_FORMATS


def test_the_start_check_is_member_wise():
    jwt_ring = f"{NEW_J},{OLD_J}"
    fernet_ring = f"{NEW_F},{OLD_F}"
    assert not shipped_secrets.secret_problems(
        {"AUTH_JWT_SECRET": jwt_ring}, {"AUTH_AES_HEX_KEY": fernet_ring}
    )
    published = "published-in-an-old-readme"
    import hashlib

    deny = {hashlib.sha256(published.encode()).hexdigest()}
    problems = shipped_secrets.secret_problems(
        {"AUTH_JWT_SECRET": f"{NEW_J},{published * 3}"[:200]}, None, deny
    )
    # a ring whose second member is not a published value passes; a published member does not
    assert not problems
    problems = shipped_secrets.secret_problems(
        {"AUTH_JWT_SECRET": published}, {"AUTH_AES_HEX_KEY": f"{NEW_F},not-a-key"}, deny
    )
    assert any("published" in p for p in problems)
    assert any("not a Fernet key" in p for p in problems)
    # a member never appears in a message
    assert not any(NEW_F in p or published in p for p in problems)
    assert shipped_secrets.secret_problems(None, {"AUTH_AES_HEX_KEY": f"{OLD_F},{OLD_F}"})


# ------------------------------------------------------------------- Fernet
def test_single_key_crypto_is_unchanged():
    crypto = Crypto(OLD_F)
    sealed = crypto.encrypt("value")
    assert Fernet(OLD_F).decrypt(sealed.encode()) == b"value"
    assert crypto.decrypt(sealed) == "value"
    assert isinstance(crypto, Fernet) and crypto.member_count == 1
    with pytest.raises(ValueError):
        Crypto("")
    with pytest.raises(ValueError):
        Crypto("not a key")


def test_ring_crypto_seals_with_the_first_and_opens_with_either():
    old_sealed = Crypto(OLD_F).encrypt("sealed under the old key")
    ring = Crypto(f"{NEW_F},{OLD_F}")
    assert ring.member_count == 2
    assert ring.decrypt(old_sealed) == "sealed under the old key"
    assert ring.opening_position(old_sealed) == 1
    assert ring.opening_member(old_sealed) == OLD_F
    fresh = ring.encrypt("sealed under the new key")
    assert ring.opening_position(fresh) == 0 and ring.opening_member(fresh) == NEW_F
    # the new key alone reads the new value, not the old one; the old key the reverse
    assert Crypto(NEW_F).decrypt(fresh) == "sealed under the new key"
    with pytest.raises(InvalidToken):
        Crypto(NEW_F).decrypt(old_sealed)
    with pytest.raises(InvalidToken):
        Crypto(OLD_F).decrypt(fresh)
    # a key that is in neither opens nothing
    assert ring.opening_position(Crypto(THIRD_F).encrypt("x")) is None
    assert ring.opening_member("not a token") is None


def test_ring_crypto_honours_ttl():
    ring = Crypto(f"{NEW_F},{OLD_F}")
    sealed = Crypto(OLD_F).encrypt("state")
    assert ring.decrypt(sealed, ttl=60) == "state"
    time.sleep(1.1)
    with pytest.raises(InvalidToken):
        ring.decrypt(sealed, ttl=0)
    assert ring.opening_member(sealed, ttl=0) is None
    assert ring.opening_member(sealed, ttl=60) == OLD_F


def test_a_ring_with_a_bad_member_fails_at_construction():
    with pytest.raises(ValueError):
        Crypto(f"{NEW_F},not-a-key")


def test_the_workers_carry_identical_ring_ciphers():
    """The Temporal workers do not depend on common; they carry the ring-aware
    ``Crypto`` as identical copies (tested in temporal/actions-executor/tests)."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    worker = (repo / "temporal/worker/configs/crypto.py").read_text()
    executor = (repo / "temporal/actions-executor/configs/crypto.py").read_text()
    assert worker == executor
    assert "MultiFernet" in worker


# ------------------------------------------- one parser, byte-identical single keys
def test_a_single_signing_secret_is_returned_exactly_as_it_is():
    """No trimming of what signs sessions and keys stored hashes: a stack that
    never rotates behaves byte for byte as before rings existed."""
    for raw in (f" {OLD_J}", f"{OLD_J}\n", f"'{OLD_J}'", "short,with,commas", f"{OLD_J},", f",{OLD_J}"):
        assert key_ring.token_members(raw) == [raw], raw
        assert shipped_secrets.token_members(raw) == [raw], raw
    assert key_ring.token_members("   ") == [] and key_ring.token_members(None) == []
    # a real ring is still read, whatever surrounds it
    assert key_ring.token_members(f" {NEW_J},{OLD_J}\n") == [NEW_J, OLD_J]


@pytest.mark.parametrize("wrap", ["{}", "'{}'", '"{}"', " {} "])
def test_both_parsers_agree_on_a_quoted_fernet_key_and_the_cipher_uses_it(wrap):
    """One rule for the cipher, the PKCE verifiers and the sign-in code hash (they all go
    through ``fernet_members``): a quoted key is the key, not a second spelling."""
    value = wrap.format(OLD_F)
    assert key_ring.fernet_members(value) == shipped_secrets.fernet_members(value) == [OLD_F]
    assert Crypto(value).decrypt(Crypto(OLD_F).encrypt("x")) == "x"
    ring = f"'{NEW_F},{OLD_F}'"
    assert key_ring.fernet_members(ring) == shipped_secrets.fernet_members(ring) == [NEW_F, OLD_F]


def test_the_start_check_says_what_a_comma_in_a_signing_secret_means(caplog):
    import logging

    caplog.set_level(logging.WARNING, logger="common.shipped_secrets")
    shipped_secrets.require_secrets(
        "test", {"AUTH_JWT_SECRET": f"{NEW_J},{OLD_J}"}, {"AUTH_AES_HEX_KEY": f"{NEW_F},{OLD_F}"}
    )
    ring_text = caplog.text
    assert "AUTH_JWT_SECRET is read as a key ring of two" in ring_text
    assert "AUTH_AES_HEX_KEY is read as a key ring of two" in ring_text
    caplog.clear()
    hand_made = "a-hand-made-secret,with-a-comma-of-some-length-0123456789"
    shipped_secrets.require_secrets("test", {"AUTH_JWT_SECRET": hand_made}, {"AUTH_AES_HEX_KEY": OLD_F})
    assert "AUTH_JWT_SECRET contains a comma but is not a key ring" in caplog.text
    hand_made_text = caplog.text
    caplog.clear()
    shipped_secrets.require_secrets("test", {"AUTH_JWT_SECRET": OLD_J}, {"AUTH_AES_HEX_KEY": OLD_F})
    assert caplog.text == ""  # a plain key is silent
    for member in (OLD_J, NEW_J, OLD_F, NEW_F, hand_made):
        assert member not in ring_text + hand_made_text


def test_the_ring_mark_fits_the_heartbeat_fingerprint():
    import re

    # settings.report_state accepts ^[A-Za-z0-9_.:-]{0,64}$ for the fingerprint
    assert re.fullmatch(r"[A-Za-z0-9_.:-]{0,64}", "ks-0123456789ab" + key_ring.REPORT_MARK)
