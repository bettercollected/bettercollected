import base64

import pytest

from backend.admin.config import (
    DATABASE_URL_KEY,
    MASTER_KEY_KEY,
    AdminConfigError,
    AdminSettings,
    parse_master_key,
)
from backend.admin.security.keys import admin_key, derive_key
from common.settings.crypto.keys import MasterKeyError

ADMIN_PURPOSES = ("audit", "pepper", "totp")

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
    raw = bytes([251, 255, 254, 250, 3, 77, 129, 200] * 4)[:32]
    assert parse_master_key(base64.urlsafe_b64encode(raw).decode()) == raw
    assert parse_master_key(base64.b64encode(raw).decode()) == raw


@pytest.mark.parametrize("raw", [bytes(32), b"a" * 48, bytes([251, 255, 254] * 11)[:32]])
def test_refuses_a_key_of_nearly_identical_bytes_without_showing_it(raw):
    value = base64.b64encode(raw).decode()
    with pytest.raises(AdminConfigError) as raised:
        parse_master_key(value)
    assert value not in str(raised.value) and "random" in str(raised.value)


@pytest.mark.parametrize("url", [None, "", "mysql://u:p@h/db", "http://x"])
def test_refuses_a_bad_database_url_without_printing_it(url):
    with pytest.raises(AdminConfigError) as raised:
        AdminSettings.from_env({DATABASE_URL_KEY: url, MASTER_KEY_KEY: GOOD})
    assert DATABASE_URL_KEY in str(raised.value)
    if url:
        assert url not in str(raised.value)


def test_subkeys_differ_per_purpose_and_are_stable():
    env = {MASTER_KEY_KEY: GOOD}
    keys = {p: derive_key("admin", p, env=env) for p in ADMIN_PURPOSES}
    assert len(set(keys.values())) == len(ADMIN_PURPOSES)
    assert all(len(k) == 32 for k in keys.values())
    assert keys == {p: admin_key(p, env=env) for p in ADMIN_PURPOSES}
    assert derive_key("admin", "audit", 2, env=env) != keys["audit"]


def test_namespaces_purposes_and_contexts_are_independent_and_open():
    env = {MASTER_KEY_KEY: GOOD}
    keys = [
        derive_key("admin", "audit", env=env),
        derive_key("settings", "audit", env=env),
        derive_key("settings", "sign", env=env),
        derive_key("settings", "wrap", 1, "smtp", env=env),
        derive_key("settings", "wrap", 1, "admin_mail", env=env),
        derive_key("tasks", "request", env=env),
    ]
    assert len(set(keys)) == len(keys)
    assert derive_key("settings", "wrap", 1, "smtp", env=env) == keys[3]
    assert derive_key("settings", "wrap", 1, None, env=env) != keys[3]


def test_subkeys_depend_on_the_master_key():
    other = base64.b64encode(bytes(range(1, 49))).decode()
    assert admin_key("audit", env={MASTER_KEY_KEY: GOOD}) != admin_key(
        "audit", env={MASTER_KEY_KEY: other}
    )


@pytest.mark.parametrize(
    "args",
    [
        ("admin", "Audit"),
        ("", "audit"),
        ("admin", ""),
        ("admin/x", "audit"),
        ("admin", "audit", 0),
        ("admin", "audit", True),
        ("admin", "audit", 1, "bad context!"),
        ("admin", "audit", 1, ""),
    ],
)
def test_bad_names_versions_or_contexts_are_refused(args):
    with pytest.raises(ValueError):
        derive_key(*args, env={MASTER_KEY_KEY: GOOD})


def test_derive_key_without_a_master_key_refuses():
    with pytest.raises(MasterKeyError):
        derive_key("admin", "audit", env={})
