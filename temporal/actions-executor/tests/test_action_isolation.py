"""``run_action`` under the isolation (the default): what a form creator's
settings can and cannot make the executor do, and that the executor needs no
key when the backend opened the secrets."""

import asyncio
import json

import pytest

from settings.application import settings
from utilities import actions, egress
from utilities.google_service import RunScope

ACTION_ID = "act-1"
HOOK = "https://hooks.acme.example/in/abc"


def run(action, workspace=None, form_extra=None, **kwargs):
    form = {
        "builder_version": "v2",
        "form_id": "f1",
        "title": "Survey",
        "welcome_page": {"title": "Survey", "description": ""},
        "fields": [],
        **(form_extra or {}),
    }
    workspace = {
        "id": "w1",
        "title": "Acme",
        "workspace_name": "acme",
        **(workspace or {}),
    }
    response = {"dataOwnerIdentifier": "respondent@example.org", "answers": {}}
    return asyncio.run(
        actions.run_action(
            json.dumps(action),
            json.dumps(form),
            json.dumps(response),
            workspace=json.dumps(workspace),
            **kwargs,
        )
    )


def hook_action(name="send_webhook", action_parameters=None, secrets=None):
    return {
        "id": ACTION_ID,
        "name": name,
        "predefined": True,
        "parameters": action_parameters or [],
        "secrets": secrets or [],
    }


def workspace_url(url, key="Webhook URL"):
    return {"parameters": {ACTION_ID: [{"name": key, "value": url}]}}


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return egress.Reply(200, b"ok")

    monkeypatch.setattr(egress, "post", post)
    return calls


@pytest.fixture
def connections(monkeypatch):
    """Records the address a connection is made to, and refuses it."""
    made = []

    def connect(self, host, port, **kwargs):
        made.append(host)
        raise egress.httpcore.ConnectError("stop")

    monkeypatch.setattr(egress.httpcore.SyncBackend, "connect_tcp", connect)
    return made


def test_a_webhook_goes_through_the_egress_rules(sent):
    run(hook_action(), workspace=workspace_url(HOOK))
    assert sent[0][0] == HOOK
    assert sent[0][1]["json_body"] == []  # no fields in this form


@pytest.mark.parametrize("name", ["send_webhook", "send_to_slack", "send_to_discord"])
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8001/api/v1/temporal/delete/submissions/x",
        "https://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "https://backend:8001/",
        "http://app-postgres:5432/",
        "https://10.0.0.5/",
    ],
)
def test_a_creators_address_never_reaches_an_internal_service(
    name, url, connections, monkeypatch
):
    # what the names of this stack resolve to
    inward = {
        "localhost": "127.0.0.1",
        "backend": "172.18.0.5",
        "app-postgres": "172.18.0.2",
    }
    monkeypatch.setattr(
        egress, "resolve", lambda host, port: [inward.get(host, "93.184.216.34")]
    )
    key = {
        "send_webhook": "Webhook URL",
        "send_to_slack": "Slack Webhook URL",
        "send_to_discord": "Discord Webhook URL",
    }[name]
    with pytest.raises(egress.EgressRefused):
        run(hook_action(name), workspace=workspace_url(url, key))
    assert connections == []


def test_a_name_that_resolves_inward_is_not_connected_to(monkeypatch, connections):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["10.0.0.5"])
    with pytest.raises(egress.EgressRefused) as refused:
        run(hook_action(), workspace=workspace_url(HOOK))
    assert refused.value.code == "not_allowed"
    assert connections == []


def test_the_administrators_own_internal_address_still_works(monkeypatch, connections):
    # an address in the action's own parameters is the instance's choice
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["10.0.0.5"])
    action = hook_action(
        action_parameters=[
            {"name": "Webhook URL", "value": "https://hooks.corp.example/in"}
        ]
    )
    with pytest.raises(egress.EgressRefused) as stopped:
        run(action)
    assert stopped.value.code == "unreachable"  # the connection was attempted
    assert connections == ["10.0.0.5"]
    # ... but a workspace cannot name one of its own next to it
    connections.clear()
    with pytest.raises(egress.EgressRefused) as refused:
        run(action, workspace=workspace_url("https://other.corp.example/in"))
    assert refused.value.code == "not_allowed" and connections == []


def test_the_operators_allow_list_is_honoured(monkeypatch, connections):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["10.0.0.5"])
    monkeypatch.setattr(settings, "action_egress_allow", "hooks.internal")
    with pytest.raises(egress.EgressRefused) as stopped:
        run(hook_action(), workspace=workspace_url("http://hooks.internal/in"))
    assert stopped.value.code == "unreachable" and connections == ["10.0.0.5"]


def test_legacy_isolation_leaves_the_calls_as_they_were(monkeypatch):
    monkeypatch.setattr(settings, "action_isolation", "legacy")
    calls = []
    monkeypatch.setattr(
        actions.httpx, "post", lambda **kwargs: calls.append(kwargs["url"])
    )
    run(hook_action(), workspace=workspace_url("http://127.0.0.1:8001/x"))
    assert calls == ["http://127.0.0.1:8001/x"]


class _NoCipher:
    """Opening or sealing anything with it is a failure of the test."""

    def __getattr__(self, name):
        raise AssertionError("the cipher was used: this run needs no key")


def test_secrets_the_backend_opened_need_no_key(monkeypatch):
    monkeypatch.setattr(actions, "crypto", _NoCipher())
    action = hook_action(
        "custom",
        secrets=[{"name": "Password", "value": "plain-password"}],
    )
    action["predefined"] = False
    action["action_code"] = "log(str(get_secret('Password')))\n"
    result = run(action, secrets_plain=True)
    assert result["log"] == "<secret Password>"
    assert "plain-password" not in result["log"]


def test_without_a_key_the_executor_starts_and_a_sealed_secret_fails_naming_it():
    import os
    import subprocess
    import sys

    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("AES_HEX_KEY", "VIRTUAL_ENV")
    }
    env["API_KEY"] = "ci-test-only-api-key"
    code = (
        "from configs.cipher import crypto\n"
        "import utilities.actions, utilities.google_service\n"
        "print('imported')\n"
        "try:\n"
        "    crypto.decrypt('gAAAAAB-sealed')\n"
        "except Exception as error:\n"
        "    print(type(error).__name__, 'AES_HEX_KEY' in str(error))\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); " + code],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        timeout=60,
    )
    assert done.stdout.split() == [
        "imported",
        "InsecureSecretError",
        "True",
    ], done.stderr


def test_a_refreshed_credential_is_handed_back_in_plain_for_the_backend_to_seal(
    monkeypatch,
):
    from utilities import google_service

    seen = {}

    class Reply:
        status_code = 200

    def patch(**kwargs):
        seen.update(kwargs)
        return Reply()

    monkeypatch.setattr(google_service.httpx, "patch", patch)
    monkeypatch.setattr(settings, "api_key", "job-key")
    google_service.writeback_for(RunScope("w1", "f1", "a1", "r 1", "tok"))(
        {"token": "t"}
    )
    assert seen["url"].endswith(
        "/temporal/workspaces/w1/forms/f1/actions/a1/runs/r%201/secrets"
    )
    assert seen["headers"] == {"api-key": "job-key", "run-token": "tok"}
    assert json.loads(seen["json"]["value"]) == {"token": "t"}
    assert seen["json"]["name"] == "Credentials"
