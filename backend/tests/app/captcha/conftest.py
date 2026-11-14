import json

import pytest

from backend.app.container import container
from backend.app.services.captcha import challenge as ch
from backend.config import settings
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.controllers.data import testUser1
from tests.app.registration.helpers import publish

# the test client connects from 127.0.0.1: the proxy whose X-Forwarded-For is believed
ALICE = {"X-Forwarded-For": "203.0.113.7"}
BOB = {"X-Forwarded-For": "198.51.100.23"}


@pytest.fixture(autouse=True)
def easy_and_proxied(monkeypatch):
    """A small difficulty keeps the Python solver quick (the browser's is the
    same work, faster), and the test client counts as the trusted proxy."""
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 14)
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")
    service = container.captcha_service()
    from backend.app.services.captcha.pressure import Pressure

    monkeypatch.setattr(service, "pressure", Pressure())


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)


@pytest.fixture()
def off(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", False)


@pytest.fixture()
def claims(monkeypatch):
    """Every call of the single-use claim."""
    calls = []
    limiter = container.rate_limiter()
    real = limiter.claim

    async def spy(scope, key, expires_at):
        calls.append(scope)
        return await real(scope, key, expires_at)

    monkeypatch.setattr(limiter, "claim", spy)
    return calls


def challenge_url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}/captcha/challenge"


def submit_url(workspace, form) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/response"


async def ask(client, workspace, form, headers=None, cookies=None, purpose="submit"):
    return await client.post(
        challenge_url(workspace),
        json={"purpose": purpose, "formId": str(form.form_id)},
        headers=headers or ALICE,
        cookies=cookies,
    )


async def submit(client, workspace, form, proof=None, headers=None, cookies=None):
    sent = dict(headers or ALICE)
    if proof is not None:
        sent[ch.HEADER] = proof
    return await client.post(
        submit_url(workspace, form),
        data={"response": json.dumps({"answers": {}})},
        headers=sent,
        cookies=cookies,
    )


async def solved(client, workspace, form, headers=None, cookies=None) -> str:
    """A proof for the form, from a challenge the route issued."""
    answer = await ask(client, workspace, form, headers, cookies)
    assert answer.status_code == 200, answer.text
    text = answer.json()["challenge"]
    return ch.proof(text, ch.solve(text))


async def a_form(workspace):
    return await publish(workspace)


def signed_in():
    return _cookies(testUser1)
