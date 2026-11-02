"""AES_HEX_KEY (the stack's AUTH_AES_HEX_KEY) must be set, a Fernet key and
not a value published in the repository, or the executor does not start."""

import base64
import hashlib

import pytest

import settings.shipped_secrets as shipped
from settings.application import ApplicationSettings, require_aes_hex_key
from settings.shipped_secrets import InsecureSecretError

GOOD_FERNET = base64.urlsafe_b64encode(b"e" * 32).decode()
# Stands in for a published value: the real ones are only known by their hash.
PUBLISHED = base64.urlsafe_b64encode(b"p" * 32).decode()


def configured(monkeypatch, value):
    monkeypatch.setenv("AES_HEX_KEY", value)
    return ApplicationSettings(_env_file=None)


def test_own_key_passes(monkeypatch):
    require_aes_hex_key(configured(monkeypatch, GOOD_FERNET))


@pytest.mark.parametrize(
    "value, problem",
    [
        ("", "AES_HEX_KEY is not set"),
        ("not-a-key", "AES_HEX_KEY is not a Fernet key"),
        (PUBLISHED, "AES_HEX_KEY is a value that was published"),
    ],
)
def test_refused(monkeypatch, value, problem):
    monkeypatch.setattr(
        shipped,
        "SHIPPED_SECRET_SHA256",
        shipped.SHIPPED_SECRET_SHA256
        | {hashlib.sha256(PUBLISHED.encode()).hexdigest()},
    )
    with pytest.raises(InsecureSecretError) as error:
        require_aes_hex_key(configured(monkeypatch, value))
    assert "Refusing to start the actions-executor" in str(error.value)
    assert problem in str(error.value)
    assert PUBLISHED not in str(error.value)


# ACTION_EXECUTOR_KEY_ALLOWED: the executor never holds the encryption key next to
# the API key once the operator turns the allowance off -----------------------------


def with_flags(monkeypatch, **env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return ApplicationSettings(_env_file=None)


def test_the_key_is_allowed_by_default_for_the_upgrade(monkeypatch):
    from settings.application import refuse_key_when_not_allowed

    monkeypatch.delenv("ACTION_EXECUTOR_KEY_ALLOWED", raising=False)
    current = with_flags(monkeypatch, AES_HEX_KEY=GOOD_FERNET)
    assert current.action_executor_key_allowed is True
    refuse_key_when_not_allowed(current)  # no exit


def test_with_the_allowance_off_the_key_stops_the_executor(monkeypatch):
    from settings.application import refuse_key_when_not_allowed

    current = with_flags(
        monkeypatch, AES_HEX_KEY=GOOD_FERNET, ACTION_EXECUTOR_KEY_ALLOWED="false"
    )
    with pytest.raises(SystemExit) as stopped:
        refuse_key_when_not_allowed(current)
    message = str(stopped.value)
    assert "AES_HEX_KEY" in message and "ACTION_EXECUTOR_KEY_ALLOWED" in message
    assert GOOD_FERNET not in message


@pytest.mark.parametrize(
    "env",
    [
        {"AES_HEX_KEY": ""},  # no key: nothing to refuse
        {"AES_HEX_KEY": GOOD_FERNET, "ACTION_ISOLATION": "legacy"},  # the way back
    ],
)
def test_the_refusal_applies_to_a_key_under_enforce_only(monkeypatch, env):
    from settings.application import refuse_key_when_not_allowed

    current = with_flags(monkeypatch, ACTION_EXECUTOR_KEY_ALLOWED="false", **env)
    refuse_key_when_not_allowed(current)


def test_the_start_log_exits_on_the_key_when_it_is_not_allowed(monkeypatch):
    import asyncio

    from sandbox import broker
    from settings.application import settings
    from utilities.isolation_log import log_isolation

    async def probe(**kwargs):
        return {"filesystem": "landlock", "seccomp": True, "unprivileged": True}

    monkeypatch.setattr(broker, "probe", probe)
    monkeypatch.setattr(settings, "aes_hex_key", "set")
    monkeypatch.setattr(settings, "action_executor_key_allowed", False)
    with pytest.raises(SystemExit):
        asyncio.run(log_isolation(key_needed=False))
    # the Temporal path gets sealed secrets by design: it is not refused here
    asyncio.run(log_isolation(key_needed=True))


def test_the_postgres_entry_point_does_not_start_with_the_key(monkeypatch):
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.update(
        JOBS_BACKEND="postgres",
        DATABASE_URL="postgresql://nobody@127.0.0.1:1/none",
        API_KEY="ci-test-only-api-key",
        AES_HEX_KEY=GOOD_FERNET,
        ACTION_EXECUTOR_KEY_ALLOWED="false",
    )
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import runpy, sys; sys.path.insert(0, '.'); "
            "runpy.run_path('main.py', run_name='__main__')",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        timeout=60,
    )
    assert done.returncode != 0
    assert "ACTION_EXECUTOR_KEY_ALLOWED" in done.stderr
    assert GOOD_FERNET not in done.stderr + done.stdout
