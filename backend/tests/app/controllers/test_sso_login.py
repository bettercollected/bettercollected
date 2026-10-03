"""Enterprise SSO through Polis (spike, docs/sso-spike.md): the backend half.
Auth is faked; it owns the Polis exchange and the email-domain check."""

import http.cookies
from typing import Any, Coroutine
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from beanie import PydanticObjectId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.workspace import WorkspaceDocument
from backend.config import settings
from common.exceptions.http import HTTPException as CommonHTTPException
from tests.app.controllers.data import testUser

SSO_USER_ID = "6a00000000000000000000aa"
REFERER = "http://localhost:3000/login"


class FakeAuth:
    """Auth's /auth/sso/basic and /auth/sso/basic/callback."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    async def get(self, url, params=None, **kwargs):
        self.calls.append((url, params))
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture
def fake_auth(monkeypatch):
    def install(**kwargs):
        fake = FakeAuth(**kwargs)
        monkeypatch.setattr(container.auth_service(), "http_client", fake)
        return fake

    return install


def sso_user(user_id=SSO_USER_ID, email="jane@example.com"):
    # FORM_RESPONDER only: keeps the personal-workspace side effect out of it
    return {
        "id": user_id,
        "sub": email,
        "roles": ["FORM_RESPONDER"],
        "plan": "FREE",
        "email_verified": True,
    }


def cookies_of(response):
    jar = {}
    for header in response.headers.get_list("set-cookie"):
        for key, morsel in http.cookies.SimpleCookie(header).items():
            jar[key] = morsel.value
    return jar


def sso_error_of(response):
    return parse_qs(urlsplit(response.headers["location"]).query).get("sso_error")


async def test_login_redirects_to_polis(client: AsyncClient, fake_auth):
    fake = fake_auth(reply={"auth_url": "http://polis.test/api/oauth/authorize?x=1"})
    response = await client.get(
        "/api/v1/auth/sso/login",
        params={"email": "jane@example.com", "creator": "true"},
        headers={"referer": REFERER},
    )
    assert response.status_code == 307
    assert response.headers["location"] == "http://polis.test/api/oauth/authorize?x=1"
    url, params = fake.calls[0]
    assert url.endswith("/auth/sso/basic")
    assert params["login_hint"] == "jane@example.com"
    assert params["client_referer_url"] == REFERER


async def test_login_for_an_unmapped_domain_returns_with_an_error(client, fake_auth):
    fake_auth(
        error=CommonHTTPException(404, {"code": "sso_not_configured", "message": "x"})
    )
    response = await client.get(
        "/api/v1/auth/sso/login",
        params={"email": "jane@nowhere.test"},
        headers={"referer": REFERER + "?type=x"},
    )
    assert response.status_code == 307
    assert response.headers["location"].startswith(REFERER)
    assert sso_error_of(response) == ["sso_not_configured"]
    assert cookies_of(response) == {}


async def test_callback_signs_in_and_joins_the_workspace(
    client: AsyncClient, fake_auth, workspace: Coroutine[Any, Any, WorkspaceDocument]
):
    fake_auth(
        reply={
            "user": sso_user(),
            "client_referer_url": REFERER,
            "sso_workspace_id": str(workspace.id),
        }
    )
    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "c", "state": "s"}
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        f"http://localhost:3000/{workspace.workspace_name}/dashboard/forms"
    )
    claims = jwt.decode(
        cookies_of(response)["Authorization"],
        settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
    )
    assert claims["sub"] == "jane@example.com"
    assert claims["email_verified"] is True
    member = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(SSO_USER_ID)
    )
    assert member.roles == ["COLLABORATOR"]

    # a second sign-in keeps the one membership
    await client.get("/api/v1/auth/sso/callback", params={"code": "c", "state": "s"})
    users = await container.workspace_user_repo().get_workspace_users(workspace.id)
    assert [str(u.user_id) for u in users].count(SSO_USER_ID) == 1


async def test_callback_leaves_an_existing_role_alone(client, fake_auth, workspace):
    # the owner (ADMIN) signing in through SSO stays ADMIN
    fake_auth(
        reply={
            "user": sso_user(testUser.id, testUser.sub),
            "client_referer_url": REFERER,
            "sso_workspace_id": str(workspace.id),
        }
    )
    await client.get("/api/v1/auth/sso/callback", params={"code": "c", "state": "s"})
    member = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(testUser.id)
    )
    assert member.roles == ["ADMIN"]


async def test_refused_email_gets_no_session(client, fake_auth):
    fake_auth(
        error=CommonHTTPException(
            403,
            {
                "code": "sso_email_domain_not_allowed",
                "message": "x",
                "client_referer_url": REFERER,
            },
        )
    )
    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "c", "state": "s"}
    )
    assert response.status_code == 307
    assert response.headers["location"].startswith(REFERER)
    assert sso_error_of(response) == ["sso_email_domain_not_allowed"]
    assert cookies_of(response) == {}


async def test_unknown_workspace_gets_no_session(client, fake_auth):
    fake_auth(
        reply={
            "user": sso_user(),
            "client_referer_url": REFERER,
            "sso_workspace_id": "65e5501d00000000000000ff",
        }
    )
    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "c", "state": "s"}
    )
    assert sso_error_of(response) == ["sso_workspace_unavailable"]
    assert cookies_of(response) == {}


@pytest.mark.parametrize("params", [{"error": "access_denied"}, {"code": "c"}, {}])
async def test_idp_errors_and_missing_params_get_no_session(client, fake_auth, params):
    fake = fake_auth(reply={})
    response = await client.get("/api/v1/auth/sso/callback", params=params)
    assert sso_error_of(response) == ["sso_failed"]
    assert cookies_of(response) == {}
    assert fake.calls == []


async def test_free_text_error_codes_are_not_reflected(client, fake_auth):
    fake_auth(
        error=CommonHTTPException(
            403, {"code": "<script>", "client_referer_url": REFERER}
        )
    )
    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "c", "state": "s"}
    )
    assert sso_error_of(response) == ["sso_failed"]
