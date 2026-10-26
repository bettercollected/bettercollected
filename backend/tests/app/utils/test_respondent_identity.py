"""The respondent identity: v2 = HMAC-SHA256(key, md5_hex(email)).

Keys here are generated per run; the repository holds none."""

import base64
import hashlib
import hmac
import secrets

import pytest

from backend.app.utils import respondent_identity as identity
from backend.app.utils.hash import hash_string

EMAIL = "respondent@example.org"


def new_key() -> bytes:
    return secrets.token_bytes(32)


def reference(key: bytes, email: str) -> str:
    """The formula, written out from the specification."""
    md5_hex = hashlib.md5(email.encode("utf-8")).hexdigest()
    return "v2:" + hmac.new(key, md5_hex.encode("utf-8"), hashlib.sha256).hexdigest()


def test_the_identity_is_hmac_of_todays_md5_hex():
    key = new_key()
    value = identity.identity_of(EMAIL, key)
    assert value == reference(key, EMAIL)
    assert value.startswith("v2:") and len(value) == 3 + 64
    # the MD5 step is exactly what hash_string has always computed
    assert hash_string(EMAIL) == hashlib.md5(EMAIL.encode()).hexdigest()


def test_input_normalisation_is_the_one_of_today():
    """No case folding or trimming was ever applied to user.sub: so none is now,
    and a stored MD5 converts to the value a sign-in computes."""
    key = new_key()
    assert identity.identity_of("A@x.org", key) != identity.identity_of("a@x.org", key)
    assert identity.identity_of(" a@x.org", key) != identity.identity_of("a@x.org", key)
    for email in ("a@x.org", "A@X.ORG", "ünï@x.org"):
        assert identity.convert_legacy(key, hash_string(email)) == identity.identity_of(
            email, key
        )


def test_a_different_key_is_a_different_identity():
    assert identity.identity_of(EMAIL, new_key()) != identity.identity_of(EMAIL, new_key())


def test_the_md5_alone_no_longer_identifies_anyone():
    """Knowing an address is no longer enough to compute the stored value."""
    key = new_key()
    stored = identity.identity_of(EMAIL, key)
    assert stored != hash_string(EMAIL)
    assert hash_string(EMAIL) not in stored


def test_matching_accepts_only_the_same_email_with_the_same_key():
    key = new_key()
    stored = identity.identity_of(EMAIL, key)
    assert identity.matches(stored, EMAIL, key)
    assert not identity.matches(stored, "other@example.org", key)
    assert not identity.matches(stored, EMAIL, new_key())


@pytest.mark.parametrize("stored", [None, "", "v2:", "v2:abc", "V2:" + "0" * 64])
def test_matching_refuses_what_is_not_this_users_v2_value(stored):
    assert not identity.matches(stored, EMAIL, new_key())


def test_matching_refuses_a_legacy_value_with_no_md5_fallback(caplog):
    """A stored value without the v2 prefix is a bug: even the exact MD5 of the
    signed-in address does not match."""
    key = new_key()
    assert not identity.matches(hash_string(EMAIL), EMAIL, key)
    assert not identity.matches(hash_string(EMAIL).upper(), EMAIL, key)


def test_matching_compares_in_constant_time(monkeypatch):
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(
        identity.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b)
    )
    key = new_key()
    assert identity.matches(identity.identity_of(EMAIL, key), EMAIL, key)
    assert calls


def test_a_v2_value_converts_to_itself():
    key = new_key()
    value = identity.identity_of(EMAIL, key)
    assert identity.convert_legacy(key, value) == value


# ----------------------------------------------------------------- the key


def test_hex_and_base64_keys_decode_to_their_bytes():
    raw = new_key()
    assert identity.key_bytes(raw.hex()) == raw
    assert identity.key_bytes(base64.b64encode(raw).decode()) == raw
    assert identity.key_bytes(base64.urlsafe_b64encode(raw).decode()) == raw
    assert identity.key_bytes(f"  {raw.hex()}\n") == raw


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "short",
        secrets.token_hex(31),  # 31 bytes
        "a" * 64,  # 32 bytes, all alike
        "changeme",
        "not hex or base64 !!! " + "x" * 40,
        "0123456789abcdef" * 4,  # a repeated block
        bytes(range(32)).hex(),  # a counting sequence
        secrets.token_hex(32) + "0",  # odd number of hex digits
        "correcthorsebatterystaplecorrecthorsebatterystaple",  # a lower-case passphrase that is valid base64
    ],
    ids=[
        "none", "empty", "blank", "short", "31-bytes", "all-alike", "placeholder", "garbage",
        "repeated-block", "counting", "odd-hex", "passphrase",
    ],
)
def test_an_unusable_key_is_refused_without_echoing_it(value):
    with pytest.raises(identity.IdentityKeyError) as raised:
        identity.key_bytes(value)
    if value and value.strip():
        assert value not in str(raised.value)


def test_the_decode_rules_are_the_documented_ones():
    raw = new_key()
    hexed = raw.hex()
    assert identity.key_bytes(hexed.upper()) == raw  # hex digits in either case
    b64 = base64.b64encode(raw).decode()
    assert identity.key_bytes(b64.rstrip("=")) == raw  # padding optional
    assert identity.key_bytes(base64.urlsafe_b64encode(raw).decode().rstrip("=")) == raw
    # text of only hex digits is hex, never base64: 64 digits are 32 bytes, not 48
    assert len(identity.key_bytes(hexed)) == 32


def test_a_non_v2_value_is_logged_once_per_interval(monkeypatch):
    from loguru import logger

    monkeypatch.setattr(identity, "_last_warning", [float("-inf")])
    lines = []
    sink = logger.add(lines.append, format="{level}|{message}")
    try:
        key = new_key()
        for _ in range(5):
            assert not identity.matches(hash_string(EMAIL), EMAIL, key)
        assert sum(m.startswith("WARNING") for m in map(str, lines)) == 1
        later = identity.time.monotonic() + identity.WARN_INTERVAL_SECONDS + 1
        monkeypatch.setattr(identity.time, "monotonic", lambda: later)
        assert not identity.matches(hash_string(EMAIL), EMAIL, key)
        assert sum(m.startswith("WARNING") for m in map(str, lines)) == 2
    finally:
        logger.remove(sink)
    assert hash_string(EMAIL) not in "".join(map(str, lines))


def test_the_key_check_is_a_label_hmac_that_is_not_an_identity():
    key = new_key()
    value = identity.key_check_value(key)
    assert value == hmac.new(key, identity.KEY_CHECK_LABEL, hashlib.sha256).hexdigest()
    assert identity.fingerprint_of(value) == value[:8]
    assert value != identity.key_check_value(new_key())
    assert not value.startswith("v2:")


def test_require_identity_key_refuses_a_missing_or_short_key():
    identity.require_identity_key("the backend", secrets.token_hex(32))
    for bad in ("", None, secrets.token_hex(16)):
        with pytest.raises(identity.IdentityKeyError, match="Refusing to start the backend"):
            identity.require_identity_key("the backend", bad)


def test_the_key_never_reaches_a_printed_settings_object():
    from backend.config import settings

    assert settings.respondent_identity.KEY
    assert settings.respondent_identity.KEY not in repr(settings.respondent_identity)
    assert settings.respondent_identity.KEY not in repr(settings)
