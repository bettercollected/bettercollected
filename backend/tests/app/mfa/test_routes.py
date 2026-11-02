"""The second-factor routes: who may call them, what they return and keep."""

import logging

import pytest
from common.security import totp

from backend.app.container import container
from backend.config import settings
from tests.app.mfa.helpers import signed_in

BASE = "/api/v1/auth/mfa"


def code_for(secret: str) -> str:
    import time

    return totp.hotp(totp.decode_secret(secret), totp.step_for(time.time()))


async def test_every_route_needs_a_signed_in_user(client, totp_on):
    for method, path in (
        ("GET", "/status"),
        ("POST", "/totp/enrol"),
        ("POST", "/totp/confirm"),
        ("POST", "/verify"),
        ("POST", "/recovery-codes"),
        ("POST", "/totp/disable"),
    ):
        reply = await client.request(method, BASE + path, json={})
        assert reply.status_code == 401, (method, path)


async def test_a_respondent_scoped_session_is_refused(client, totp_on):
    account = await signed_in()
    user = account.user.model_copy(
        update={"session_scope": "respondent", "scope_workspace_id": "0" * 24}
    )
    from backend.app.services.auth_cookie_service import access_token_for

    token = access_token_for(user)
    reply = await client.get(
        BASE + "/status", cookies={"Authorization": token, "RefreshToken": token}
    )
    assert reply.status_code == 403


async def test_the_switch_off_answers_422_everywhere_but_the_status(client):
    assert settings.totp.ENABLED is False  # off unless a test turns it on
    account = await signed_in()
    status = await client.get(BASE + "/status", cookies=account.cookies)
    assert status.status_code == 200
    assert status.json() == {"available": False, "enabled": False, "recoveryLeft": None}
    for path in ("/totp/enrol", "/totp/confirm", "/verify", "/recovery-codes", "/totp/disable"):
        body = {"factorId": "x", "code": "123456"} if path == "/totp/confirm" else {}
        reply = await client.post(BASE + path, cookies=account.cookies, json=body)
        assert reply.status_code == 422, path
        assert reply.json()["code"] == "totp_off", path


async def test_enrol_confirm_verify_and_disable_over_http(client, totp_on, caplog):
    caplog.set_level(logging.DEBUG)
    account = await signed_in()
    enrol = await client.post(BASE + "/totp/enrol", cookies=account.cookies, json={})
    assert enrol.status_code == 200, enrol.text
    assert enrol.headers["cache-control"] == "no-store"
    body = enrol.json()
    assert set(body) == {"factorId", "secret", "uri", "qr"}
    secret = "".join(body["secret"].split())

    wrong = await client.post(
        BASE + "/totp/confirm",
        cookies=account.cookies,
        json={"factorId": body["factorId"], "code": "000000"},
    )
    assert wrong.status_code == 422 and wrong.json()["code"] == "invalid_code"

    confirmed = await client.post(
        BASE + "/totp/confirm",
        cookies=account.cookies,
        json={"factorId": body["factorId"], "code": code_for(secret)},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.headers["cache-control"] == "no-store"
    codes = confirmed.json()["recoveryCodes"]
    assert len(codes) == 10

    status = await client.get(BASE + "/status", cookies=account.cookies)
    assert status.json() == {"available": True, "enabled": True, "recoveryLeft": 10}
    assert status.headers.get("cache-control") != "public"

    # a recovery code in place of a code, once
    verified = await client.post(
        BASE + "/verify", cookies=account.cookies, json={"code": codes[0]}
    )
    assert verified.status_code == 200 and verified.json()["recoveryLeft"] == 9
    replay = await client.post(
        BASE + "/verify", cookies=account.cookies, json={"code": codes[0]}
    )
    assert replay.status_code == 422

    disabled = await client.post(
        BASE + "/totp/disable", cookies=account.cookies, json={"code": codes[1]}
    )
    assert disabled.status_code == 200 and disabled.json()["enabled"] is False

    # nothing secret reached a log line
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert secret not in logged and not any(c in logged for c in codes)


async def test_a_code_longer_than_any_code_is_refused_before_it_is_looked_at(client, totp_on):
    account = await signed_in()
    reply = await client.post(
        BASE + "/verify", cookies=account.cookies, json={"code": "1" * 41}
    )
    assert reply.status_code == 422
    assert "totp_off" not in reply.text


async def test_an_old_session_gets_recent_proof_required(client, totp_on):
    account = await signed_in(age_minutes=30)
    reply = await client.post(BASE + "/totp/enrol", cookies=account.cookies, json={})
    assert reply.status_code == 403
    assert reply.json()["code"] == "recent_proof_required"
    assert await container.user_totp_repo().pending(account.user.id) is None


async def test_the_confirm_body_cannot_name_another_accounts_factor(client, totp_on):
    mine = await signed_in("mine@example.org")
    theirs = await signed_in("theirs@example.org")
    enrol = (
        await client.post(BASE + "/totp/enrol", cookies=mine.cookies, json={})
    ).json()
    secret = "".join(enrol["secret"].split())
    reply = await client.post(
        BASE + "/totp/confirm",
        cookies=theirs.cookies,
        json={"factorId": enrol["factorId"], "code": code_for(secret)},
    )
    assert reply.status_code == 422 and reply.json()["code"] == "invalid_code"
