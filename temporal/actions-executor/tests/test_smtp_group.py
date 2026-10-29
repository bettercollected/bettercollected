"""The SMTP settings of a mail action come from one side only: the
instance's defaults, or the workspace/form, never mixed name by name. A
workspace that overrides only the server must never have the instance's login
sent to its server."""

import asyncio
import json

import pytest
from cryptography.fernet import Fernet

from settings.application import settings

if not settings.aes_hex_key:
    settings.aes_hex_key = Fernet.generate_key().decode()

from configs.crypto import crypto  # noqa: E402
from utilities import actions  # noqa: E402
from utilities.smtp_group import (  # noqa: E402
    SmtpConfigurationError,
    in_smtp_group,
    smtp_settings,
)

ACTION_ID = "act-1"
INSTANCE_PASSWORD = "instance-pw-7f3a"
OWN_PASSWORD = "workspace-pw-91c2"

INSTANCE = {
    "Username": "instance-user",
    "Sender": "noreply@instance.example",
    "Port": "587",
    "server": "smtp.instance.example",
}
OWN = {
    "Username": "acme-user",
    "Sender": "forms@acme.example",
    "Port": "2525",
    "server": "smtp.acme.example",
}


def _param(name, value):
    return {"name": name, "value": value}


def _action(name="responder_copy_mail", **extra):
    return {
        "id": ACTION_ID,
        "name": name,
        "predefined": True,
        "parameters": [_param(k, v) for k, v in {**INSTANCE, **extra}.items()],
        "secrets": [_param("Password", crypto.encrypt(INSTANCE_PASSWORD))],
    }


def _owner(values=None, secrets=None):
    owner = {
        "parameters": {ACTION_ID: [_param(k, v) for k, v in (values or {}).items()]}
    }
    if secrets:
        owner["secrets"] = {
            ACTION_ID: [_param(k, crypto.encrypt(v)) for k, v in secrets.items()]
        }
    return owner


class _Capture:
    """What the SMTP client is built with."""

    configs = []

    def __init__(self, config):
        self.config = config

    async def send_message(self, message, template_name=None):
        pass


@pytest.fixture(autouse=True)
def _capture(monkeypatch):
    _Capture.configs = []
    real_init = _Capture.__init__

    def init(self, config):
        real_init(self, config)
        _Capture.configs.append(config)

    monkeypatch.setattr(_Capture, "__init__", init)
    monkeypatch.setattr(actions, "FastMail", _Capture)


def _run(action, workspace=None, form_extra=None):
    workspace = {"title": "Acme", **(workspace or {})}
    form = {
        "builder_version": "v2",
        "title": "Survey",
        "welcome_page": {"title": "Survey", "description": ""},
        "fields": [],
        **(form_extra or {}),
    }
    response = {"dataOwnerIdentifier": "respondent@example.org", "answers": {}}

    async def go():
        await actions.run_action(
            json.dumps(action),
            json.dumps(form),
            json.dumps(response),
            workspace=json.dumps(workspace),
        )
        await asyncio.sleep(0)

    asyncio.run(go())
    return _Capture.configs


def _used(config):
    return {
        "server": config.MAIL_SERVER,
        "port": config.MAIL_PORT,
        "username": config.MAIL_USERNAME,
        "password": config.MAIL_PASSWORD.get_secret_value(),
        "sender": config.MAIL_FROM,
    }


INSTANCE_USED = {
    "server": "smtp.instance.example",
    "port": 587,
    "username": "instance-user",
    "password": INSTANCE_PASSWORD,
    "sender": "noreply@instance.example",
}
OWN_USED = {
    "server": "smtp.acme.example",
    "port": 2525,
    "username": "acme-user",
    "password": OWN_PASSWORD,
    "sender": "forms@acme.example",
}


def test_no_override_uses_the_instances_defaults():
    (config,) = _run(_action(), {})
    assert _used(config) == INSTANCE_USED


def test_full_override_uses_only_the_override():
    (config,) = _run(_action(), _owner(OWN, {"Password": OWN_PASSWORD}))
    assert _used(config) == OWN_USED


def test_full_override_on_the_form_uses_only_the_override():
    (config,) = _run(_action(), {}, _owner(OWN, {"Password": OWN_PASSWORD}))
    assert _used(config) == OWN_USED


def test_workspace_and_form_together_are_one_side():
    (config,) = _run(
        _action(),
        _owner({k: OWN[k] for k in ("server", "Port")}),
        _owner({k: OWN[k] for k in ("Username", "Sender")}, {"Password": OWN_PASSWORD}),
    )
    assert _used(config) == OWN_USED


def test_only_the_server_never_gets_the_instances_login():
    # the finding: the workspace's server must not receive the instance's
    # user name, password, sender or port
    with pytest.raises(SmtpConfigurationError) as raised:
        _run(_action(), _owner({"server": "smtp.acme.example"}))
    assert _Capture.configs == []
    message = str(raised.value)
    for missing in ("Port", "Username", "Password", "Sender"):
        assert missing in message
    for leaked in (INSTANCE_PASSWORD, "instance-user", "smtp.instance.example"):
        assert leaked not in message


@pytest.mark.parametrize(
    "workspace_values, workspace_secrets",
    [
        ({"Sender": "forms@acme.example"}, None),
        ({"Username": "acme-user"}, None),
        ({"Port": "2525"}, None),
        # a password alone must not be sent to the instance's server either
        ({}, {"Password": OWN_PASSWORD}),
        # spelled differently: still an attempt to set the group
        ({"Server": "smtp.acme.example"}, None),
    ],
)
def test_any_one_member_switches_the_whole_group(workspace_values, workspace_secrets):
    with pytest.raises(SmtpConfigurationError):
        _run(_action(), _owner(workspace_values, workspace_secrets))
    assert _Capture.configs == []


def test_a_partial_form_override_does_not_borrow_from_the_instance():
    with pytest.raises(SmtpConfigurationError):
        _run(_action(), {}, _owner({"server": "smtp.acme.example"}))
    assert _Capture.configs == []


def test_empty_override_values_are_no_override():
    (config,) = _run(
        _action(), _owner({"server": "", "Username": "", "Sender": ""}, None)
    )
    assert _used(config) == INSTANCE_USED


def test_another_actions_overrides_do_not_count():
    other = {"parameters": {"other-action": [_param("server", "evil.example")]}}
    (config,) = _run(_action(), other)
    assert _used(config) == INSTANCE_USED


def test_the_creators_copy_follows_the_same_rule(monkeypatch):
    # who may be mailed is tests/test_copy_recipient.py; here it is allowed
    monkeypatch.setattr(actions, "approved_copy_recipient", lambda address, *_: address)
    action = _action(
        "creator_copy_mail", **{"Receiving Mail Address": "own@acme.example"}
    )
    with pytest.raises(SmtpConfigurationError):
        _run(action, _owner({"server": "smtp.acme.example"}))
    assert _Capture.configs == []
    # an override of something that is not SMTP leaves the instance's mailer
    (config,) = _run(
        _action("creator_copy_mail"),
        _owner({"Receiving Mail Address": "own@acme.example"}),
    )
    assert _used(config) == INSTANCE_USED


def test_other_parameters_still_merge_by_name():
    action = _action(**{"Webhook URL": "https://instance.example/hook", "Note": "a"})
    workspace = _owner({"Note": "b", "server": "smtp.acme.example"})
    # through custom action code, which reads the merged values itself
    action["predefined"] = False
    action["action_code"] = (
        "log(get_parameter('Note'))\n"
        "log(get_parameter('Webhook URL'))\n"
        "log(get_parameter('server'))\n"
        "log(get_parameter('Username'))\n"
        "log(get_secret('Password'))\n"
    )
    result = asyncio.run(
        actions.run_action(
            json.dumps(action),
            json.dumps({"builder_version": "v2", "title": "Survey"}),
            json.dumps({"answers": {}}),
            workspace=json.dumps(workspace),
        )
    )
    assert result["log"].split("\n") == [
        "b",
        "https://instance.example/hook",
        "smtp.acme.example",
        "None",
        "None",
    ]


def test_custom_action_code_gets_the_same_rule():
    action = _action()
    action["predefined"] = False
    action["action_code"] = (
        "log(get_parameter('Username'))\nlog(get_secret('Password'))\n"
    )
    result = asyncio.run(
        actions.run_action(
            json.dumps(action),
            json.dumps({"builder_version": "v2", "title": "Survey"}),
            json.dumps({"answers": {}}),
            workspace=json.dumps(_owner({"server": "smtp.acme.example"})),
        )
    )
    assert result["log"] == "None\nNone"
    no_override = asyncio.run(
        actions.run_action(
            json.dumps(action),
            json.dumps({"builder_version": "v2", "title": "Survey"}),
            json.dumps({"answers": {}}),
            workspace=json.dumps({}),
        )
    )
    assert no_override["log"] == "instance-user\n" + INSTANCE_PASSWORD


def test_the_refusal_names_settings_never_values(capsys):
    with pytest.raises(SmtpConfigurationError) as raised:
        _run(_action(), _owner({"server": "smtp.acme.example"}))
    seen = str(raised.value) + capsys.readouterr().out
    for secret in (INSTANCE_PASSWORD, "instance-user", "noreply@instance.example"):
        assert secret not in seen


def test_smtp_settings_reports_missing_and_bad_port():
    full = {**INSTANCE}
    assert smtp_settings(full, {"Password": "x"}) == (
        "instance-user",
        "x",
        "noreply@instance.example",
        587,
        "smtp.instance.example",
    )
    with pytest.raises(SmtpConfigurationError, match="missing: Password"):
        smtp_settings(full, {})
    with pytest.raises(SmtpConfigurationError, match="not a number"):
        smtp_settings({**full, "Port": "abc"}, {"Password": "x"})


@pytest.mark.parametrize(
    "name, member",
    [
        ("server", True),
        ("Server", True),
        ("Port", True),
        ("Username", True),
        ("Password", True),
        ("Sender", True),
        ("SMTP Host", True),
        ("smtp_tls", True),
        ("Webhook URL", False),
        ("Receiving Mail Address", False),
        ("Google Sheet Id", False),
        (None, False),
    ],
)
def test_group_membership(name, member):
    assert in_smtp_group(name) is member
