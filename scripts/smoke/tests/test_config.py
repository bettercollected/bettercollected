import pytest

from smoke import config
from tests.conftest import API_KEY, APP_PASSWORD, CLIENT_SECRET, REFRESH_TOKEN

GMAIL = {
    "SMOKE_GMAIL_CLIENT_ID": "1234-fake.apps.googleusercontent.com",
    "SMOKE_GMAIL_CLIENT_SECRET": CLIENT_SECRET,
    "SMOKE_GMAIL_REFRESH_TOKEN": REFRESH_TOKEN,
}


def test_imap_mailbox(base_env):
    loaded = config.load(
        {**base_env, "SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD}, tag="smoke-1"
    )
    assert loaded.mailbox.kind == config.IMAP
    assert loaded.mailbox.imap_host == "imap.gmail.com"
    assert loaded.run_address == "smoke+smoke-1@gmail.com"
    assert loaded.api_url is None
    assert set(loaded.secrets()) == {API_KEY, APP_PASSWORD}


def test_gmail_api_mailbox(base_env):
    loaded = config.load({**base_env, **GMAIL})
    assert loaded.mailbox.kind == config.GMAIL_API
    assert REFRESH_TOKEN in loaded.secrets() and CLIENT_SECRET in loaded.secrets()


@pytest.mark.parametrize(
    "extra, message",
    [
        ({}, "no mailbox is configured"),
        ({"SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD, **GMAIL}, "both mailbox sets"),
        (
            {"SMOKE_GMAIL_CLIENT_ID": "x", "SMOKE_GMAIL_REFRESH_TOKEN": REFRESH_TOKEN},
            "SMOKE_GMAIL_CLIENT_SECRET not set",
        ),
    ],
    ids=["neither", "both", "incomplete-gmail"],
)
def test_exactly_one_mailbox_set(base_env, extra, message):
    with pytest.raises(config.ConfigError) as error:
        config.load({**base_env, **extra})
    assert message in str(error.value)
    for secret in (APP_PASSWORD, REFRESH_TOKEN, CLIENT_SECRET, API_KEY):
        assert secret not in str(error.value)


def test_blank_values_count_as_unset(base_env):
    env = {**base_env, "SMOKE_IMAP_APP_PASSWORD": "  ", **{k: "" for k in GMAIL}}
    with pytest.raises(config.ConfigError, match="no mailbox"):
        config.load(env)


@pytest.mark.parametrize(
    "name",
    [
        "SMOKE_APP_URL",
        "SMOKE_API_KEY",
        "SMOKE_MAILBOX",
        "SMOKE_WORKSPACE_ID",
        "SMOKE_CUSTOM_DOMAIN",
        "SMOKE_GOOGLE_FORM_ID",
    ],
)
def test_each_variable_is_required(base_env, name):
    env = {**base_env, "SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD}
    del env[name]
    with pytest.raises(config.ConfigError, match=name):
        config.load(env)


@pytest.mark.parametrize(
    "name, value",
    [
        ("SMOKE_APP_URL", "admin.example.com"),
        ("SMOKE_APP_URL", "https://user:pw@admin.example.com"),
        ("SMOKE_API_KEY", "not-a-key"),
        ("SMOKE_MAILBOX", "smoke+already@gmail.com"),
        ("SMOKE_WORKSPACE_ID", "a b"),
        ("SMOKE_CUSTOM_DOMAIN", "https://forms.example.org"),
        ("SMOKE_GOOGLE_FORM_ID", "https://docs.google.com/forms/d/x/edit"),
    ],
    ids=[
        "no-scheme",
        "credentials",
        "key",
        "plus-mailbox",
        "workspace",
        "domain-scheme",
        "form-url",
    ],
)
def test_malformed_values_are_refused_without_echo(base_env, name, value):
    env = {**base_env, "SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD, name: value}
    with pytest.raises(config.ConfigError) as error:
        config.load(env)
    assert value not in str(error.value)


def test_workspace_accepts_an_id_or_a_name(base_env):
    env = {**base_env, "SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD}
    for value in ("6add1ec59947c7bd75b36282", "smoke-test", "smoke_test.2"):
        assert config.load({**env, "SMOKE_WORKSPACE_ID": value}).workspace == value


def test_imap_needs_gmail(base_env):
    env = {
        **base_env,
        "SMOKE_MAILBOX": "smoke@example.org",
        "SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD,
    }
    with pytest.raises(config.ConfigError, match="Gmail"):
        config.load(env)


def test_mailpit_dry_run_refuses_real_mailbox_secrets(base_env):
    loaded = config.load(
        base_env, mailpit_url="http://localhost:8025", target="http://localhost:3000"
    )
    assert loaded.mailbox.kind == config.MAILPIT
    assert loaded.app_url == "http://localhost:3000"
    with pytest.raises(config.ConfigError, match="dry run"):
        config.load(
            {**base_env, "SMOKE_IMAP_APP_PASSWORD": APP_PASSWORD},
            mailpit_url="http://localhost:8025",
        )


def test_run_tags_are_unique_and_valid():
    env = {"GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "2"}
    tags = {config.run_tag(env) for _ in range(20)}
    assert len(tags) == 20
    for tag in tags:
        assert tag.startswith("smoke-123456-2-")
        config.plus_address("smoke@gmail.com", tag)
    assert config.run_tag({}).startswith("smoke-local-")


def test_secrets_never_in_repr(base_env):
    loaded = config.load({**base_env, **GMAIL})
    text = repr(loaded)
    for secret in (API_KEY, REFRESH_TOKEN, CLIENT_SECRET):
        assert secret not in text
