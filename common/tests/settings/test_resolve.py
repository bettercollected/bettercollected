import pytest

from common.settings.registry import default_registry
from common.settings.resolve import ResolveError, Source, resolve

from settings_support import plain_row, secret_row

REG = default_registry(secret_problems=lambda k, v: [])
PORT = REG.get("MAIL_SMTP_PORT")


def port(env, row=None, default=587):
    return resolve("MAIL_SMTP_PORT", env, row, default, REG)


def test_env_beats_store_beats_default():
    row = plain_row(value=2525)
    got = port({"MAIL_SMTP_PORT": "465"}, row)
    assert (got.value, got.source, got.overridden_by_env) == (465, Source.ENV, True)
    got = port({}, row)
    assert (got.value, got.source, got.overridden_by_env) == (2525, Source.STORE, False)
    got = port({})
    assert (got.value, got.source, got.overridden_by_env) == (587, Source.DEFAULT, False)


@pytest.mark.parametrize("empty", ["", " ", "\t", "''", '""', "' '", None])
def test_an_empty_env_value_is_unset(empty):
    got = port({"MAIL_SMTP_PORT": empty}, plain_row(value=2525))
    assert (got.value, got.source) == (2525, Source.STORE)
    got = port({"MAIL_SMTP_PORT": empty})
    assert got.source is Source.DEFAULT


def test_env_is_normalised_before_use():
    assert port({"MAIL_SMTP_PORT": ' "465" '}).value == 465
    assert port({"MAIL_SMTP_PORT": "'465'"}).value == 465


def test_a_bad_env_value_is_an_error_not_a_silent_fallback():
    with pytest.raises(ResolveError) as raised:
        port({"MAIL_SMTP_PORT": "needle"}, plain_row(value=2525))
    assert "needle" not in str(raised.value)


def test_env_values_get_type_checks_not_url_policy():
    env = {"AI_COMPAT_BASE_URL": "http://localhost:11434/v1"}  # a dev setup
    got = resolve("AI_COMPAT_BASE_URL", env, None, None, REG)
    assert got.source is Source.ENV and got.value == env["AI_COMPAT_BASE_URL"]


def test_unknown_key_and_mismatched_row():
    with pytest.raises(Exception):
        resolve("NOPE", {}, None, None, REG)
    with pytest.raises(ResolveError):
        resolve("MAIL_SMTP_PORT", {}, plain_row(key="MAIL_SMTP_SERVER", value="x"), 1, REG)


def test_stored_value_is_rechecked():
    with pytest.raises(ResolveError):
        port({}, plain_row(value=70000))


def test_secrets_are_opened_lazily_and_only_from_the_store(keys):
    row = secret_row(keys)
    calls = []

    def opener(r):
        calls.append(r.key)
        return keys.open(r.section, r.key, r.version, r.blob)

    got = resolve("MAIL_PASSWORD", {}, row, None, REG, open_secret=opener)
    assert (got.value, got.source) == ("smtp-pass-1", Source.STORE) and calls == ["MAIL_PASSWORD"]

    calls.clear()
    got = resolve(
        "MAIL_PASSWORD", {"MAIL_PASSWORD": "from-env"}, row, None, REG, open_secret=opener
    )
    assert (got.value, got.source, got.overridden_by_env) == ("from-env", Source.ENV, True)
    got = resolve("MAIL_PASSWORD", {}, None, None, REG, open_secret=opener)
    assert got.source is Source.DEFAULT
    assert calls == []  # never opened


def test_an_unopenable_secret_fails_without_leaking(keys):
    row = secret_row(keys)
    with pytest.raises(ResolveError) as raised:
        resolve("MAIL_PASSWORD", {}, row, None, REG)  # no opener
    assert "v2:" not in str(raised.value)

    def broken(_row):
        raise RuntimeError("boom with v2:secretish")

    with pytest.raises(ResolveError) as raised:
        resolve("MAIL_PASSWORD", {}, row, None, REG, open_secret=broken)
    assert "secretish" not in str(raised.value) and raised.value.__cause__ is None


def test_repr_never_shows_the_value(keys):
    got = resolve("MAIL_PASSWORD", {"MAIL_PASSWORD": "super-secret-value"}, None, None, REG)
    assert "super-secret" not in repr(got)
