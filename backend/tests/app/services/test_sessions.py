"""Revocable sessions behind the cookie tokens (``session_service``).

Sign-in creates a session; access tokens are short-lived and checked without
it; every refresh checks it (and the user, through auth's /status), so a
revoked session ends at its next refresh. ``POST /auth/refresh`` rotates the
refresh token; replaying a rotated one revokes the session. Runs against the
routed repository, so in every store mode."""

import calendar
import datetime as dt
import http.cookies
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from starlette.requests import Request
from starlette.responses import Response

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services import session_service as session_module
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.session_service import RevokeReason, SessionEnded
from backend.app.services.user_service import (
    get_logged_user,
    get_user_if_logged_in,
)
from backend.config import settings
from common.models.user import User
from tests.app.controllers.data import testUser

pytestmark = pytest.mark.asyncio

STATUS_USERS = {}


class FakeAuth:
    """httpx.AsyncClient standing in for auth's GET /auth/status."""

    calls = []
    status_code = 200

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, headers=None, **kwargs):
        FakeAuth.calls.append(params)
        status_code = FakeAuth.status_code
        roles = ["FORM_CREATOR"] + (["ADMIN"] if params["email_verified"] else [])
        body = {
            "id": params["user_id"],
            "email": testUser.sub,
            "roles": roles,
            "plan": "PRO",
        }

        class Reply:
            @staticmethod
            def json():
                return body

        Reply.status_code = status_code
        return Reply()


@pytest.fixture(autouse=True)
def fake_auth(monkeypatch):
    monkeypatch.setattr(session_module, "auth_http_client", FakeAuth)
    FakeAuth.calls = []
    FakeAuth.status_code = 200


def set_cookies(response) -> dict:
    """Cookie name -> (value, max-age) of every Set-Cookie on a starlette or
    httpx response."""
    headers = response.headers
    listed = getattr(headers, "getlist", None) or headers.get_list
    found = {}
    for header in listed("set-cookie"):
        cookie = http.cookies.SimpleCookie(header)
        for key, morsel in cookie.items():
            found[key] = (morsel.value, morsel["max-age"])
    return found


def issued(reply, name: str) -> str:
    return set_cookies(reply)[name][0]


def claims(token: str) -> dict:
    return jwt.decode(
        token,
        settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_exp": False},
    )


def request_with(**cookies) -> Request:
    cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
    return Request(
        {
            "type": "http",
            "method": "GET",
            "query_string": b"",
            "headers": [(b"cookie", cookie.encode())],
        }
    )


async def sign_in(user: User = testUser, verified: bool = True):
    """A new session: (tokens by cookie name, sid)."""
    response = Response()
    await container.session_service().start(
        user.model_copy(update={"email_verified": verified}), response
    )
    cookies = {k: v for k, (v, _) in set_cookies(response).items()}
    return cookies, claims(cookies["RefreshToken"])["sid"]


async def stored(sid: str):
    return await container.session_repo().get(sid)


def expired_access(refresh: str) -> dict:
    return {"Authorization": "expired", "RefreshToken": refresh}


# -- sign-in ------------------------------------------------------------------


async def test_sign_in_creates_a_session_named_in_both_tokens():
    tokens, sid = await sign_in(verified=True)
    session = await stored(sid)
    assert session.user_id == testUser.id
    assert session.email_verified is True
    assert session.revoked_at is None
    access, refresh = claims(tokens["Authorization"]), claims(tokens["RefreshToken"])
    assert access["sid"] == refresh["sid"] == sid
    assert (access["typ"], refresh["typ"]) == ("access", "refresh")
    assert refresh["jti"] == session.refresh_jti
    lifetime = access["exp"] - calendar.timegm(
        dt.datetime.now(dt.timezone.utc).utctimetuple()
    )
    assert lifetime <= settings.auth_settings.ACCESS_TOKEN_EXPIRY_IN_MINUTES * 60


async def test_a_live_access_token_needs_no_session_read(monkeypatch):
    tokens, sid = await sign_in()
    monkeypatch.setattr(
        container.session_service(), "refresh", AsyncMock(side_effect=AssertionError)
    )
    user = await get_logged_user(request_with(**tokens), Response())
    assert (user.id, user.sid) == (testUser.id, sid)


# -- refresh ------------------------------------------------------------------


async def test_an_expired_access_token_is_refreshed_through_the_session():
    tokens, sid = await sign_in(verified=True)
    response = Response()
    request = request_with(**expired_access(tokens["RefreshToken"]))

    user = await get_logged_user(request, response)

    assert (user.id, user.sid, user.email_verified) == (testUser.id, sid, True)
    assert "ADMIN" in user.roles  # status asked with the session's claim
    assert FakeAuth.calls == [{"user_id": testUser.id, "email_verified": True}]
    issued = set_cookies(response)
    assert claims(issued["Authorization"][0])["sid"] == sid
    # the implicit refresh never rotates (server-side rendering drops cookies)
    assert "RefreshToken" not in issued
    assert request.state.access_token == issued["Authorization"][0]
    assert (await stored(sid)).last_refreshed_at is not None


async def test_explicit_refresh_rotates_the_refresh_token(client):
    tokens, sid = await sign_in()
    old = claims(tokens["RefreshToken"])["jti"]

    reply = await client.post("/api/v1/auth/refresh", cookies=tokens)

    assert reply.status_code == 200, reply.text
    new_refresh = issued(reply, "RefreshToken")
    rotated = claims(new_refresh)
    assert rotated["sid"] == sid and rotated["jti"] != old
    session = await stored(sid)
    assert (session.refresh_jti, session.previous_refresh_jti) == (rotated["jti"], old)
    assert claims(issued(reply, "Authorization"))["sid"] == sid

    # the new one keeps working and rotates again
    again = await client.post(
        "/api/v1/auth/refresh", cookies={"RefreshToken": new_refresh}
    )
    assert again.status_code == 200
    assert claims(issued(again, "RefreshToken"))["jti"] not in (old, rotated["jti"])


async def test_a_just_rotated_token_gets_only_an_access_token_in_the_grace_period(
    client,
):
    """Two tabs refreshing at once: the loser is not revoked, but it gets an
    access token alone, never the current refresh token (a stolen old token
    must not ride on the owner's rotation)."""
    tokens, sid = await sign_in()
    first = await client.post("/api/v1/auth/refresh", cookies=tokens)
    assert first.status_code == 200

    racing = await client.post("/api/v1/auth/refresh", cookies=tokens)

    assert racing.status_code == 200
    session = await stored(sid)
    assert session.revoked_at is None
    issued_now = set_cookies(racing)
    assert "RefreshToken" not in issued_now
    assert claims(issued_now["Authorization"][0])["sid"] == sid
    # the session's current token is still only the one the winner got
    assert claims(issued(first, "RefreshToken"))["jti"] == session.refresh_jti


async def test_a_session_revoked_while_auth_is_asked_gets_no_token(monkeypatch):
    tokens, sid = await sign_in()
    service = container.session_service()
    current_user = service._current_user

    async def revoke_meanwhile(session):
        user = await current_user(session)
        await service.revoke(sid, testUser.id, RevokeReason.LOGOUT_EVERYWHERE)
        return user

    monkeypatch.setattr(service, "_current_user", revoke_meanwhile)
    response = Response()
    with pytest.raises(SessionEnded):
        await get_logged_user(
            request_with(**expired_access(tokens["RefreshToken"])), response
        )
    assert set_cookies(response) == {}


async def test_replaying_a_rotated_refresh_token_revokes_the_session(
    client, monkeypatch
):
    monkeypatch.setattr(settings.auth_settings, "REFRESH_REUSE_GRACE_SECONDS", -1)
    tokens, sid = await sign_in()
    rotated = await client.post("/api/v1/auth/refresh", cookies=tokens)
    assert rotated.status_code == 200

    replay = await client.get(
        "/api/v1/auth/status", cookies=expired_access(tokens["RefreshToken"])
    )

    assert replay.status_code == 401
    session = await stored(sid)
    assert session.revoke_reason == RevokeReason.REFRESH_TOKEN_REUSE
    # the legitimate holder of the new token is signed out too
    after = await client.post(
        "/api/v1/auth/refresh",
        cookies={"RefreshToken": issued(rotated, "RefreshToken")},
    )
    assert after.status_code == 401


async def test_a_revoked_session_cannot_refresh_and_its_cookies_are_cleared(client):
    tokens, sid = await sign_in()
    await container.session_service().revoke(sid, testUser.id, RevokeReason.LOGOUT)

    reply = await client.get(
        "/api/v1/auth/status", cookies=expired_access(tokens["RefreshToken"])
    )

    assert reply.status_code == 401
    cleared = set_cookies(reply)
    assert cleared["Authorization"][1] == "0"
    assert cleared["RefreshToken"][1] == "0"
    assert FakeAuth.calls == []  # auth is not even asked
    explicit = await client.post("/api/v1/auth/refresh", cookies=tokens)
    assert explicit.status_code == 401


async def test_a_deleted_user_cannot_refresh():
    tokens, sid = await sign_in()
    FakeAuth.status_code = 404

    with pytest.raises(SessionEnded):
        await get_logged_user(
            request_with(**expired_access(tokens["RefreshToken"])), Response()
        )

    assert (await stored(sid)).revoke_reason == RevokeReason.USER_NOT_FOUND


async def test_auth_refusing_the_key_is_a_503_not_a_sign_out():
    tokens, sid = await sign_in()
    FakeAuth.status_code = 403
    with pytest.raises(HTTPException) as refused:
        await get_logged_user(
            request_with(**expired_access(tokens["RefreshToken"])), Response()
        )
    assert refused.value.status_code == 503
    assert (await stored(sid)).revoked_at is None


async def test_explicit_refresh_while_auth_refuses_is_a_503(client):
    tokens, sid = await sign_in()
    FakeAuth.status_code = 503
    reply = await client.post("/api/v1/auth/refresh", cookies=tokens)
    assert reply.status_code == 503
    assert "RefreshToken" not in set_cookies(reply)
    assert (await stored(sid)).revoked_at is None


async def test_explicit_refresh_without_cookies_is_a_plain_401(client):
    reply = await client.post("/api/v1/auth/refresh")
    assert reply.status_code == 401
    assert set_cookies(reply) == {}


async def test_an_expired_session_cannot_refresh():
    tokens, sid = await sign_in()
    session = await stored(sid)
    session.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await container.session_repo().save(session)
    with pytest.raises(SessionEnded):
        await get_logged_user(
            request_with(**expired_access(tokens["RefreshToken"])), Response()
        )


async def test_a_refresh_token_is_not_an_access_token(monkeypatch):
    tokens, sid = await sign_in()
    await container.session_service().revoke(sid, testUser.id, RevokeReason.LOGOUT)
    # presented as the access token, the (still unexpired) refresh token must
    # not skip the session check
    with pytest.raises(SessionEnded):
        await get_logged_user(
            request_with(
                Authorization=tokens["RefreshToken"],
                RefreshToken=tokens["RefreshToken"],
            ),
            Response(),
        )


# -- tokens from before sessions -----------------------------------------------


def legacy_token(**extra) -> str:
    """What the backend issued before sessions: no ``sid``, no ``typ``."""
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
    return jwt.encode(
        {
            "id": testUser.id,
            "sub": testUser.sub,
            "roles": ["FORM_CREATOR"],
            "email_verified": True,
            "exp": calendar.timegm(exp.utctimetuple()),
            "jti": "legacy",
            **extra,
        },
        settings.auth_settings.JWT_SECRET,
        algorithm="HS256",
    )


async def test_legacy_tokens_sign_the_user_out_once(client):
    token = legacy_token()
    reply = await client.get(
        "/api/v1/auth/status",
        cookies={"Authorization": token, "RefreshToken": token},
    )
    assert reply.status_code == 401
    assert set_cookies(reply)["RefreshToken"][1] == "0"
    explicit = await client.post(
        "/api/v1/auth/refresh", cookies={"RefreshToken": token}
    )
    assert explicit.status_code == 401
    assert FakeAuth.calls == []


async def test_public_pages_drop_an_ended_sessions_cookies():
    token = legacy_token()
    response = Response()
    user = await get_user_if_logged_in(
        request_with(Authorization=token, RefreshToken=token), response
    )
    assert user is None
    assert set_cookies(response)["Authorization"][1] == "0"


async def test_anonymous_requests_clear_nothing():
    response = Response()
    assert await get_user_if_logged_in(request_with(), response) is None
    assert set_cookies(response) == {}


# -- revocation ----------------------------------------------------------------


async def test_logout_revokes_the_session(client):
    tokens, sid = await sign_in()
    reply = await client.get("/api/v1/auth/logout", cookies=tokens)
    assert reply.status_code == 200
    assert (await stored(sid)).revoke_reason == RevokeReason.LOGOUT
    refresh = await client.post("/api/v1/auth/refresh", cookies=tokens)
    assert refresh.status_code == 401


async def test_logout_without_a_session_just_clears_cookies(client):
    reply = await client.get("/api/v1/auth/logout")
    assert reply.status_code == 200


async def test_sessions_list_and_logout_everywhere_else(client):
    here, current = await sign_in()
    _, laptop = await sign_in()
    _, phone = await sign_in()
    other_user = testUser.model_copy(update={"id": "5f9b1b9b9b9b9b9b9b9b9b9b"})
    _, someone_elses = await sign_in(other_user)

    listed = await client.get("/api/v1/auth/sessions", cookies=here)
    assert listed.status_code == 200, listed.text
    rows = {row["id"]: row for row in listed.json()}
    assert set(rows) == {current, laptop, phone}
    assert rows[current]["current"] is True and rows[laptop]["current"] is False
    assert {"createdAt", "lastRefreshedAt", "expiresAt", "userAgent"} <= set(
        rows[current]
    )

    # someone else's session is not mine to end
    foreign = await client.delete(
        f"/api/v1/auth/sessions/{someone_elses}", cookies=here
    )
    assert foreign.status_code == 404
    assert (await stored(someone_elses)).revoked_at is None

    one = await client.delete(f"/api/v1/auth/sessions/{laptop}", cookies=here)
    assert one.status_code == 200
    assert (await stored(laptop)).revoke_reason == RevokeReason.SIGNED_OUT_ELSEWHERE

    rest = await client.delete("/api/v1/auth/sessions", cookies=here)
    assert rest.status_code == 200 and rest.json() == {"revoked": 1}
    assert (await stored(phone)).revoke_reason == RevokeReason.LOGOUT_EVERYWHERE
    assert (await stored(current)).revoked_at is None
    assert (await stored(someone_elses)).revoked_at is None

    listed = await client.get("/api/v1/auth/sessions", cookies=here)
    assert [row["id"] for row in listed.json()] == [current]


async def test_ending_the_current_session_from_the_list_clears_its_cookies(client):
    here, current = await sign_in()
    reply = await client.delete(f"/api/v1/auth/sessions/{current}", cookies=here)
    assert reply.status_code == 200
    assert set_cookies(reply)["RefreshToken"][1] == "0"


async def test_logout_everywhere_ends_every_session_at_its_next_refresh():
    sessions = [await sign_in() for _ in range(3)]
    revoked = await container.session_service().revoke_all_for_user(
        testUser.id, RevokeReason.LOGOUT_EVERYWHERE
    )
    assert revoked == 3
    for tokens, _ in sessions:
        with pytest.raises(SessionEnded):
            await get_logged_user(
                request_with(**expired_access(tokens["RefreshToken"])), Response()
            )


@pytest.fixture
def queued_deletions(monkeypatch):
    """The deletion requests the service queues (Temporal/procrastinate)."""
    queued = []
    service = container.auth_service()

    async def start(deletion):
        queued.append(deletion)
        return "Job Started"

    monkeypatch.setattr(service.temporal_service, "start_user_deletion_workflow", start)
    monkeypatch.setattr(
        "backend.app.services.auth_service.event_logger_service",
        SimpleNamespace(send_event=AsyncMock()),
    )
    return queued


async def test_requesting_account_deletion_signs_out_everywhere(queued_deletions):
    tokens, sid = await sign_in()
    _, elsewhere = await sign_in()

    await container.auth_service().add_workflow_to_delete_user(user=testUser)

    for revoked in (sid, elsewhere):
        assert (await stored(revoked)).revoke_reason == RevokeReason.ACCOUNT_DELETED
    (deletion,) = queued_deletions
    assert (deletion.user_id, deletion.email) == (testUser.id, testUser.sub)


async def test_account_deletion_works_with_only_the_refresh_cookie(
    client, queued_deletions
):
    """More than 15 minutes after the last request the access cookie is gone:
    the deletion is still queued, naming the user (no token is stored)."""
    tokens, sid = await sign_in()
    reply = await client.post(
        "/api/v1/auth/user/delete/workflow",
        cookies={"RefreshToken": tokens["RefreshToken"]},
        json={"reasonForDeletion": "testing"},
    )
    assert reply.status_code == 200, reply.text
    (deletion,) = queued_deletions
    assert deletion.user_id == testUser.id and deletion.email == testUser.sub
    assert (await stored(sid)).revoked_at is not None


async def test_the_deletion_job_names_its_user_by_the_encrypted_request(monkeypatch):
    """The procrastinate job (and the Temporal route) take the user from the
    request the backend encrypted, so they work after every session is gone;
    and the deletion deletes the session rows."""
    import json
    from dataclasses import asdict

    from backend.app.models.dataclasses.user_tokens import UserDeletion
    from backend.jobs import tasks

    _, sid = await sign_in()
    deleted = []
    service = container.auth_service()
    monkeypatch.setattr(
        service, "delete_credentials_from_integrations", AsyncMock()
    )
    monkeypatch.setattr(service, "delete_user_form_auth", AsyncMock())

    async def delete_workspaces(user):
        deleted.append(user)

    monkeypatch.setattr(
        service.workspace_service,
        "delete_workspaces_of_user_with_forms",
        delete_workspaces,
    )
    blob = container.crypto().encrypt(
        json.dumps(asdict(UserDeletion(user_id=testUser.id, email=testUser.sub)))
    )

    await tasks.delete_user.func(encrypted_tokens=blob, user_id=testUser.id)

    assert [(u.id, u.sub) for u in deleted] == [(testUser.id, testUser.sub)]
    assert await stored(sid) is None  # deleted, not just revoked
    with pytest.raises(ValueError):
        await tasks.delete_user.func(encrypted_tokens=blob, user_id="someone-else")


async def test_the_deletion_route_takes_only_an_encrypted_request(client, monkeypatch):
    import json

    monkeypatch.setattr(settings.temporal_settings, "api_key", "job-key-for-tests")
    tokens, _ = await sign_in()
    key = {"api-key": settings.temporal_settings.api_key}
    legacy = container.crypto().encrypt(
        json.dumps(
            {
                "access_token": tokens["Authorization"],
                "refresh_token": tokens["RefreshToken"],
            }
        )
    )
    for headers in (
        key,  # no request
        {**key, "X-User-Deletion": "forged"},
        {**key, "X-User-Deletion": tokens["RefreshToken"]},
        {**key, "X-User-Deletion": legacy},  # stored tokens: refused
    ):
        reply = await client.delete(
            "/api/v1/auth/user", headers=headers, cookies=tokens
        )
        assert reply.status_code == 400, headers
    wrong_key = await client.delete(
        "/api/v1/auth/user", headers={"api-key": "nope"}, cookies=tokens
    )
    assert wrong_key.status_code == 403


async def test_expired_sessions_are_swept():
    _, old = await sign_in()
    _, live = await sign_in()
    session = await stored(old)
    session.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await container.session_repo().save(session)

    listed = await container.session_service().list_for_user(testUser.id)

    assert [str(s.id) for s in listed] == [live]
    assert await stored(old) is None


# -- what rides on a refreshed request -----------------------------------------


async def test_the_plugin_proxy_forwards_the_refreshed_access_token():
    sent = {}

    class Client:
        async def request(self, **kwargs):
            sent.update(kwargs)
            return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    request = request_with(Authorization="expired", RefreshToken="r")
    request.state.access_token = "fresh"

    await PluginProxyService(Client()).pass_request(request, "http://plugin/x")

    assert sent["cookies"]["Authorization"] == "fresh"
    assert "cookie" not in {k.lower() for k in sent["headers"]}


async def test_the_plugin_proxy_passes_cookies_unchanged_otherwise():
    sent = {}

    class Client:
        async def request(self, **kwargs):
            sent.update(kwargs)
            return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    request = request_with(Authorization="live", RefreshToken="r")
    await PluginProxyService(Client()).pass_request(request, "http://plugin/x")
    assert sent["cookies"]["Authorization"] == "live"
    assert sent["headers"] is request.headers
