"""The routes that forward the caller's cookies to a form provider's service
check the signed-in user first: without a valid access token the backend
answers 401 and forwards nothing."""

from unittest.mock import AsyncMock, patch

import jwt
import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.services.auth_cookie_service import REFRESH, access_token_for
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.config import settings
from common.models.user import User
from tests.app.controllers.data import testUser

ROOT = "/api/v1"
GOOGLE_URL = "http://google-forms.invalid"
ROUTES = [
    "/google/import/form-1",
    "/google/import",
]


@pytest.fixture()
async def google_provider_config():
    await container.form_provider_service().add_provider(
        FormProviderConfigDto(
            enabled=True,
            provider_name="google",
            provider_url=GOOGLE_URL,
            auth_callback_url=f"{GOOGLE_URL}/google/oauth/callback",
        )
    )


@pytest.fixture()
def forwarded(monkeypatch):
    """Every request the plugin proxy would forward to the Google service."""
    monkeypatch.setattr(settings.google_forms, "IMPORT", "on")
    with patch.object(
        PluginProxyService, "pass_request", AsyncMock(return_value={"ok": True})
    ) as pass_request:
        yield pass_request


def _claims(user: User, **extra) -> dict:
    return {
        "id": user.id,
        "sub": user.sub,
        "roles": user.roles,
        "plan": user.plan,
        "sid": "5f0000000000000000000001",
        "exp": 4_000_000_000,
        **extra,
    }


def _token(**extra) -> str:
    return jwt.encode(
        _claims(testUser, **extra),
        settings.auth_settings.JWT_SECRET,
        algorithm="HS256",
    )


@pytest.mark.parametrize("path", ROUTES)
async def test_without_cookies_nothing_is_forwarded(
    client: AsyncClient, google_provider_config, forwarded, path
):
    response = await client.get(ROOT + path)
    assert response.status_code == 401
    forwarded.assert_not_awaited()


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: _token(typ=REFRESH, jti="j"), id="refresh"),
        pytest.param(lambda: _token(typ="other"), id="unknown-type"),
        pytest.param(lambda: _token(), id="no-type"),
        pytest.param(lambda: "not-a-jwt", id="malformed"),
    ],
)
async def test_a_token_that_is_not_an_access_token_forwards_nothing(
    client: AsyncClient, google_provider_config, forwarded, path, token
):
    value = token()
    # presented as the access cookie, with or without the refresh cookie
    for cookies in ({"Authorization": value}, {"Authorization": value, "RefreshToken": value}):
        response = await client.get(ROOT + path, cookies=cookies)
        assert response.status_code == 401, cookies.keys()
    forwarded.assert_not_awaited()


@pytest.mark.parametrize("path", ROUTES)
async def test_a_respondent_session_forwards_nothing(
    client: AsyncClient, google_provider_config, forwarded, path
):
    token = access_token_for(
        User(
            id=testUser.id,
            sub=testUser.sub,
            sid="5f0000000000000000000001",
            session_scope="respondent",
            scope_workspace_id="5f0000000000000000000002",
        )
    )
    response = await client.get(ROOT + path, cookies={"Authorization": token})
    assert response.status_code == 403
    forwarded.assert_not_awaited()


@pytest.mark.parametrize("path", ROUTES)
async def test_an_access_token_is_forwarded(
    client: AsyncClient, google_provider_config, forwarded, test_user_cookies, path
):
    response = await client.get(ROOT + path, cookies=test_user_cookies)
    assert response.status_code == 200
    assert forwarded.await_count == 1
