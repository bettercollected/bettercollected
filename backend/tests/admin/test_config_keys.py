import base64

import pytest

from backend.admin.config import (
    DATABASE_URL_KEY,
    MASTER_KEY_KEY,
    AdminConfigError,
    AdminSettings,
    parse_master_key,
)
from backend.admin.security.keys import PURPOSES, derive_key

GOOD = base64.b64encode(bytes(range(48))).decode()
URL = "postgresql://bc_admin:s3cret-pw@db:5432/x"


def test_settings_from_a_valid_environment():
    settings = AdminSettings.from_env({DATABASE_URL_KEY: URL, MASTER_KEY_KEY: GOOD})
    assert settings.database_url.startswith("postgresql+asyncpg://bc_admin:")
    assert len(settings.master_key) == 48
    assert "s3cret-pw" not in repr(settings) and GOOD not in repr(settings)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "not base64 !!",
        base64.b64encode(bytes(31)).decode(),  # one byte short
        "a" * 7,
    ],
)
def test_refuses_a_missing_or_weak_master_key_without_printing_it(value):
    with pytest.raises(AdminConfigError) as raised:
        AdminSettings.from_env({DATABASE_URL_KEY: URL, MASTER_KEY_KEY: value})
    message = str(raised.value)
    assert MASTER_KEY_KEY in message
    if value and value.strip():
        assert value not in message


def test_accepts_url_safe_base64_and_exactly_32_bytes():
    raw = bytes([251, 255, 254] * 11)[:32]
    assert parse_master_key(base64.urlsafe_b64encode(raw).decode()) == raw
    assert parse_master_key(base64.b64encode(raw).decode()) == raw


@pytest.mark.parametrize("url", [None, "", "mysql://u:p@h/db", "http://x"])
def test_refuses_a_bad_database_url_without_printing_it(url):
    with pytest.raises(AdminConfigError) as raised:
        AdminSettings.from_env({DATABASE_URL_KEY: url, MASTER_KEY_KEY: GOOD})
    assert DATABASE_URL_KEY in str(raised.value)
    if url:
        assert url not in str(raised.value)


def test_subkeys_differ_per_purpose_and_are_stable():
    env = {MASTER_KEY_KEY: GOOD}
    keys = {p: derive_key(p, env=env) for p in PURPOSES}
    assert len(set(keys.values())) == len(PURPOSES)
    assert all(len(k) == 32 for k in keys.values())
    assert keys == {p: derive_key(p, env=env) for p in PURPOSES}
    assert derive_key("audit", 2, env=env) != keys["audit"]


def test_subkeys_depend_on_the_master_key():
    other = base64.b64encode(bytes(range(1, 49))).decode()
    assert derive_key("audit", env={MASTER_KEY_KEY: GOOD}) != derive_key(
        "audit", env={MASTER_KEY_KEY: other}
    )


def test_bad_purpose_or_version_is_refused():
    with pytest.raises(ValueError):
        derive_key("mail", env={MASTER_KEY_KEY: GOOD})
    with pytest.raises(ValueError):
        derive_key("audit", 0, env={MASTER_KEY_KEY: GOOD})


def test_derive_key_without_a_master_key_refuses():
    with pytest.raises(AdminConfigError):
        derive_key("audit", env={})
