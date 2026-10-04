"""Single sign-on, the review fixes (docs/sso.md): redirects through the
workspace handle, login CSRF and single-use states, disabled memberships,
the seat-cap race, no stored platform-admin role for SSO sessions, sessions
ending at refresh on SSO-required domains, and respondent-scoped sessions."""

import http.cookies
from urllib.parse import urlsplit

import pytest
from beanie import PydanticObjectId
from common.models.user import User
from starlette.responses import Response

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import session_service as session_module
from backend.app.services.session_service import decode_token
from backend.app.services.workspace_user_service import SeatLimitReached
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    DOMAIN,
    LOGIN_PAGE,
    add_connection,
    query_of,
    sso_on,
    state_of,
    verify_domain,
)

LOGIN = "/api/v1/auth/sso/login"
CALLBACK = "/api/v1/auth/sso/callback"


@pytest.fixture()
async def sso_workspace(workspace, sso_on):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id)
    return workspace, connection


async def start(client, email="jane@" + DOMAIN, referer=LOGIN_PAGE):
    reply = await client.get(
        LOGIN, params={"email": email}, headers={"referer": referer}
    )
    assert reply.status_code == 307, reply.text
    return reply


def sso_error(reply):
    return query_of(reply.headers["location"]).get("sso_error")


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


# -- open redirect through the workspace handle --------------------------------
@pytest.mark.parametrize(
    "handle,path",
    [
        ("//evil.com", "/%2F%2Fevil.com/dashboard/forms"),
        ("/\\evil.com", "/%2F%5Cevil.com/dashboard/forms"),
        ("%2F%2Fevil.com", "/%252F%252Fevil.com/dashboard/forms"),
        ("https://evil.com", "/https%3A%2F%2Fevil.com/dashboard/forms"),
    ],
)
async def test_a_crafted_handle_never_leaves_the_origin(
    client, sso_workspace, handle, path
):
    workspace, _ = sso_workspace
    await container.workspace_repo().set_fields(workspace, {"workspace_name": handle})
    started = await start(client)
    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    location = urlsplit(reply.headers["location"])
    assert f"{location.scheme}://{location.netloc}" == "http://localhost:3000"
    assert location.path == path


# -- login CSRF ---------------------------------------------------------------
async def test_start_sets_a_short_lived_httponly_nonce_cookie(client, sso_workspace):
    reply = await start(client)
    header = [
        v
        for k, v in reply.headers.multi_items()
        if k == "set-cookie" and "SsoNonce" in v
    ][0]
    morsel = http.cookies.SimpleCookie(header)["SsoNonce"]
    assert morsel.value and morsel["httponly"] and morsel["samesite"].lower() == "lax"
    assert int(morsel["max-age"]) <= 600
    assert morsel["path"] == "/api/v1/auth/sso"


async def test_a_callback_from_another_browser_is_refused(client, sso_workspace):
    _, auth = (
        container.sso_connection_service()._polis,
        container.sso_login_service()._http,
    )
    started = await start(client)
    client.cookies.clear()  # the victim's browser: no nonce cookie
    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    assert sso_error(reply) == "sso_session_mismatch"
    assert "Authorization" not in reply.cookies
    assert auth.created_accounts() == []


async def test_a_wrong_nonce_is_refused(client, sso_workspace):
    started = await start(client)
    client.cookies.set("SsoNonce", "forged", path="/api/v1/auth/sso")
    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    assert sso_error(reply) == "sso_session_mismatch"


async def test_a_state_is_accepted_once(client, sso_workspace):
    started = await start(client)
    nonce = client.cookies.get("SsoNonce")
    state = state_of(started.headers["location"])
    first = await client.get(CALLBACK, params={"code": "c", "state": state})
    assert "Authorization" in first.cookies and not sso_error(first)
    # replayed with the same browser's nonce
    client.cookies.set("SsoNonce", nonce, path="/api/v1/auth/sso")
    second = await client.get(CALLBACK, params={"code": "c", "state": state})
    assert sso_error(second) == "sso_session_mismatch"
    assert "Authorization" not in second.cookies


# -- memberships and seats ----------------------------------------------------
async def test_a_disabled_membership_gets_no_session(client, sso_workspace):
    workspace, _ = sso_workspace
    auth = container.sso_login_service()._http
    account = auth.add_account("jane@" + DOMAIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=account["id"],
            roles=[WorkspaceRoles.COLLABORATOR],
            disabled=True,
        )
    )
    started = await start(client)
    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    assert sso_error(reply) == "sso_membership_disabled"
    assert "Authorization" not in reply.cookies
    member = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(account["id"])
    )
    assert member.disabled is True


async def test_the_seat_race_gives_the_seat_back(workspace, monkeypatch):
    service = container.workspace_user_service()
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 0)

    async def looked_free(workspace_id):
        return True  # both racers passed the first look

    monkeypatch.setattr(service, "has_free_seat", looked_free)
    late = User(id=str(PydanticObjectId()), sub="late@" + DOMAIN)
    with pytest.raises(SeatLimitReached):
        await service.add_sso_member(workspace.id, late, WorkspaceRoles.COLLABORATOR)
    assert await service.find_member(workspace.id, late.id) is None


# -- sessions -----------------------------------------------------------------
class FakeStatus:
    """auth's /auth/status for the refresh path."""

    email = "jane@" + DOMAIN
    roles = ["FORM_RESPONDER", "FORM_CREATOR"]
    seen = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, **kwargs):
        FakeStatus.seen.append(params)
        email, roles = FakeStatus.email, FakeStatus.roles

        class Reply:
            status_code = 200

            @staticmethod
            def json():
                return {"id": params["user_id"], "email": email, "roles": roles}

        return Reply()


@pytest.fixture()
def fake_status(monkeypatch):
    FakeStatus.seen = []
    FakeStatus.email = "jane@" + DOMAIN
    FakeStatus.roles = ["FORM_RESPONDER", "FORM_CREATOR"]
    monkeypatch.setattr(session_module, "auth_http_client", FakeStatus)
    return FakeStatus


async def _refresh_token(user: User, **start) -> str:
    response = Response()
    await container.session_service().start(user, response, None, **start)
    for key, value in response.raw_headers:
        if key == b"set-cookie" and value.startswith(b"RefreshToken="):
            return http.cookies.SimpleCookie(value.decode())["RefreshToken"].value
    raise AssertionError("no refresh token")


async def refresh(client, token):
    return await client.post("/api/v1/auth/refresh", cookies={"RefreshToken": token})


async def test_an_sso_session_never_keeps_a_stored_admin_role(
    client, sso_workspace, fake_status
):
    fake_status.roles = ["FORM_RESPONDER", "FORM_CREATOR", "ADMIN"]
    jane = User(id=str(PydanticObjectId()), sub="jane@" + DOMAIN, email_verified=True)
    token = await _refresh_token(jane, method="sso")
    reply = await refresh(client, token)
    assert reply.status_code == 200, reply.text
    roles = decode_token(reply.cookies.get("Authorization"))["roles"]
    assert "ADMIN" not in roles and "FORM_CREATOR" in roles


@pytest.fixture()
async def required(client, sso_workspace):
    workspace, _ = sso_workspace
    reply = await client.put(
        f"/api/v1/workspaces/{workspace.id}/sso/settings",
        json={"ssoRequired": True},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200, reply.text
    return workspace


@pytest.mark.parametrize(
    "method,user_is_owner,scope,survives",
    [
        ("otp", False, None, False),  # a member's (or anyone's) email code
        ("google", False, None, False),
        (None, False, None, False),  # signed in before methods were recorded
        ("google", True, None, False),  # the owner's Google session too
        ("otp", True, None, True),  # break-glass
        ("sso", False, None, True),
        ("otp", False, "respondent", True),
    ],
)
async def test_refresh_ends_non_sso_sessions_on_required_domains(
    client, required, fake_status, method, user_is_owner, scope, survives
):
    workspace = required
    user_id = testUser.id if user_is_owner else str(PydanticObjectId())
    user = User(id=user_id, sub="someone@" + DOMAIN, email_verified=True)
    fake_status.email = "someone@" + DOMAIN
    extra = (
        {"scope": scope, "scope_workspace_id": str(PydanticObjectId())} if scope else {}
    )
    token = await _refresh_token(user, method=method, **extra)
    reply = await refresh(client, token)
    if survives:
        assert reply.status_code == 200, reply.text
    else:
        assert reply.status_code == 401, reply.text
        assert "single sign-on" in reply.text
        sessions = await container.session_service().list_for_user(user_id)
        assert sessions == []


async def test_refresh_leaves_other_domains_alone(client, required, fake_status):
    fake_status.email = "carol@elsewhere-corp.org"
    user = User(id=str(PydanticObjectId()), sub="carol@elsewhere-corp.org")
    token = await _refresh_token(user, method="otp")
    assert (await refresh(client, token)).status_code == 200


# -- respondent-scoped sessions ------------------------------------------------
@pytest.fixture()
async def other_workspace(required):
    other = WorkspaceDocument(
        title="Other",
        workspace_name="other-ws",
        owner_id=str(PydanticObjectId()),
        description="",
    )
    return await container.workspace_repo().save(other)


async def test_codes_stay_blocked_on_the_sso_workspaces_own_forms(
    client, required, other_workspace
):
    workspace = required
    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
        params={"receiver_email": "bob@" + DOMAIN},
    )
    assert reply.status_code == 403 and reply.json()["code"] == "sso_required"
    reply = await client.post(
        f"/api/v1/workspaces/{other_workspace.id}/auth/otp/send",
        params={"receiver_email": "bob@" + DOMAIN},
    )
    assert reply.status_code == 200, reply.text


async def test_a_code_on_another_workspace_gives_a_respondent_session_only(
    client, required, other_workspace, fake_status
):
    workspace = required
    auth = container.sso_login_service()._http
    bob = auth.add_account("bob@" + DOMAIN)
    auth.otp_user = {
        **bob,
        "email_verified": True,
        "roles": ["FORM_RESPONDER", "FORM_CREATOR", "ADMIN"],
    }
    # bob is also a member (even an admin) of the SSO workspace
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=bob["id"], roles=[WorkspaceRoles.ADMIN]
        )
    )

    # without the workspace context it is a dashboard sign-in: refused
    reply = await client.post(
        "/api/v1/auth/otp/validate", json={"email": "bob@" + DOMAIN, "otp_code": "X"}
    )
    assert reply.status_code == 403 and reply.json()["code"] == "sso_required"
    # the SSO workspace's own forms: refused
    reply = await client.post(
        "/api/v1/auth/otp/validate",
        params={"workspace_id": str(workspace.id)},
        json={"email": "bob@" + DOMAIN, "otp_code": "X"},
    )
    assert reply.status_code == 403

    reply = await client.post(
        "/api/v1/auth/otp/validate",
        params={"workspace_id": str(other_workspace.id)},
        json={"email": "bob@" + DOMAIN, "otp_code": "X"},
    )
    assert reply.status_code == 200, reply.text
    claims = decode_token(reply.cookies.get("Authorization"))
    assert claims["session_scope"] == "respondent"
    assert claims["scope_workspace_id"] == str(other_workspace.id)
    assert claims["roles"] == ["FORM_RESPONDER"]
    cookies = {
        "Authorization": reply.cookies.get("Authorization"),
        "RefreshToken": reply.cookies.get("RefreshToken"),
    }
    # no workspace permission anywhere, not even where bob is an admin
    for ws in (workspace.id, other_workspace.id):
        perms = await client.get(
            f"/api/v1/workspaces/{ws}/permissions", cookies=cookies
        )
        assert perms.status_code == 200 and perms.json()["permissions"] == []
    reply = await client.get(f"/api/v1/workspaces/{workspace.id}/sso", cookies=cookies)
    assert reply.status_code == 403
    reply = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms", cookies=cookies
    )
    assert reply.status_code == 403
    # no personal workspace was created for it
    assert (
        await container.workspace_repo().get_default_workspace_by_owner_id(bob["id"])
        is None
    )
    # exempt from the refresh rule, and stays respondent-scoped
    fake_status.email = "bob@" + DOMAIN
    fake_status.roles = ["FORM_RESPONDER", "FORM_CREATOR", "ADMIN"]
    refreshed = await refresh(client, cookies["RefreshToken"])
    assert refreshed.status_code == 200, refreshed.text
    claims = decode_token(refreshed.cookies.get("Authorization"))
    assert claims["session_scope"] == "respondent" and claims["roles"] == [
        "FORM_RESPONDER"
    ]
    assert fake_status.seen[-1]["email_verified"] is False


async def _respondent_cookies(client, required, other_workspace):
    auth = container.sso_login_service()._http
    bob = auth.add_account("bob@" + DOMAIN)
    auth.otp_user = {**bob, "email_verified": True}
    reply = await client.post(
        "/api/v1/auth/otp/validate",
        params={"workspace_id": str(other_workspace.id)},
        json={"email": "bob@" + DOMAIN, "otp_code": "X"},
    )
    assert reply.status_code == 200, reply.text
    return {
        "Authorization": reply.cookies.get("Authorization"),
        "RefreshToken": reply.cookies.get("RefreshToken"),
    }


def _refused_as_respondent(reply):
    assert reply.status_code == 403, reply.text
    assert reply.json()["code"] == "respondent_session", reply.text


async def test_a_respondent_session_cannot_create_a_workspace(
    client, required, other_workspace
):
    cookies = await _respondent_cookies(client, required, other_workspace)
    reply = await client.post(
        "/api/v1/workspaces", data={"title": "Mine"}, cookies=cookies
    )
    _refused_as_respondent(reply)


async def test_a_respondent_session_gets_no_dashboard_access(
    client, required, other_workspace
):
    workspace = required
    cookies = await _respondent_cookies(client, required, other_workspace)
    # listing is harmless, but never with dashboard access
    mine = await client.get("/api/v1/workspaces/mine", cookies=cookies)
    assert mine.status_code == 200
    assert not any(w.get("dashboardAccess") for w in mine.json())
    for ws in (workspace, other_workspace):
        reply = await client.get(
            "/api/v1/workspaces",
            params={"workspace_name": ws.workspace_name},
            cookies=cookies,
        )
        assert reply.status_code == 200 and not reply.json().get("dashboardAccess")


async def test_a_respondent_session_cannot_create_api_keys(
    client, required, other_workspace
):
    cookies = await _respondent_cookies(client, required, other_workspace)
    reply = await client.post(
        f"/api/v1/workspaces/{other_workspace.id}/api-keys",
        json={"name": "k", "scopes": ["forms:read"]},
        cookies=cookies,
    )
    assert reply.status_code == 403


async def test_a_respondent_session_cannot_start_an_import_oauth(
    client, required, other_workspace
):
    cookies = await _respondent_cookies(client, required, other_workspace)
    _refused_as_respondent(
        await client.get("/api/v1/auth/google/oauth", cookies=cookies)
    )
    _refused_as_respondent(
        await client.get(
            "/api/v1/auth/google/oauth/callback",
            params={"code": "c", "state": "s"},
            cookies=cookies,
        )
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/user/tags/details"),
        ("POST", "/api/v1/actions"),
        ("GET", "/api/v1/stripe/session/create/checkout"),
        ("GET", "/api/v1/admin/metrics"),
        ("POST", "/api/v1/coupons/redeem/X"),
    ],
)
async def test_a_respondent_session_is_refused_beyond_forms(
    client, required, other_workspace, method, path
):
    cookies = await _respondent_cookies(client, required, other_workspace)
    reply = await client.request(method, path, cookies=cookies)
    assert reply.status_code in (403, 404, 405, 422), reply.text
    if reply.status_code == 403:
        assert "respondent" in reply.text or "not authorized" in reply.text


async def test_a_respondent_session_keeps_its_own_respondent_paths(
    client, required, other_workspace, fake_status
):
    cookies = await _respondent_cookies(client, required, other_workspace)
    fake_status.email = "bob@" + DOMAIN
    sessions = await client.get("/api/v1/auth/sessions", cookies=cookies)
    assert sessions.status_code == 200 and sessions.json()[0]["scope"] == "respondent"
    reply = await client.get(
        f"/api/v1/workspaces/{other_workspace.id}/submissions", cookies=cookies
    )
    assert reply.status_code != 403 or "respondent_session" not in reply.text


async def test_without_sso_required_a_code_is_a_full_session(
    client, sso_workspace, other_workspace_plain
):
    auth = container.sso_login_service()._http
    bob = auth.add_account("bob@" + DOMAIN)
    auth.otp_user = {**bob, "email_verified": True}
    reply = await client.post(
        "/api/v1/auth/otp/validate",
        params={"workspace_id": str(other_workspace_plain.id)},
        json={"email": "bob@" + DOMAIN, "otp_code": "X"},
    )
    assert reply.status_code == 200
    assert "session_scope" not in decode_token(reply.cookies.get("Authorization"))


@pytest.fixture()
async def other_workspace_plain(sso_workspace):
    return await container.workspace_repo().save(
        WorkspaceDocument(
            title="Plain", workspace_name="plain-ws", owner_id=str(PydanticObjectId())
        )
    )
