"""Provider sign-ins that auth refuses, and the import-OAuth token exchange
(#758): a refused sign-in goes back to the login page with a reason and no
session; the import flow never moves the session to another account."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.app.exceptions import HTTPException
from backend.app.services.auth_service import AuthService, with_login_error
from common.models.user import User


def _service(**deps) -> AuthService:
    service = AuthService.__new__(AuthService)
    for name, dep in deps.items():
        setattr(service, name, dep)
    return service


def test_login_error_is_added_to_the_login_page_url():
    url = with_login_error(
        "https://admin.example.com/login?type=responder&login_error=old",
        "unverified_email",
        "google",
    )
    parts = urlsplit(url)
    assert parts.netloc == "admin.example.com" and parts.path == "/login"
    assert parse_qs(parts.query) == {
        "type": ["responder"],
        "login_error": ["unverified_email"],
        "login_provider": ["google"],
    }


@pytest.mark.parametrize("code", ["<script>", "Unverified Email", "", None, 3])
def test_only_plain_codes_are_passed_on(code):
    assert with_login_error("https://x.test/login", code, "google") == (
        "https://x.test/login"
    )


def test_no_page_to_return_to_stays_empty():
    assert with_login_error("", "unverified_email", "google") == ""


async def test_a_refused_sign_in_redirects_with_the_reason_and_no_user():
    http_client = SimpleNamespace(
        get=AsyncMock(
            return_value={
                "client_referer_url": "https://admin.example.com/login",
                "creator": True,
                "error": "unverified_email",
                "provider": "google",
            }
        )
    )
    tags = SimpleNamespace(add_user_tag=AsyncMock())
    service = _service(http_client=http_client, user_tags_service=tags)

    user, url = await service.basic_auth_callback("google", "code", "state")

    assert user is None
    query = parse_qs(urlsplit(url).query)
    assert query == {"login_error": ["unverified_email"], "login_provider": ["google"]}
    tags.add_user_tag.assert_not_awaited()


async def test_import_oauth_refuses_another_accounts_email_before_the_exchange():
    signed_in = User(id="u1", sub="me@example.com", roles=["FORM_RESPONDER"])
    form_provider_service = SimpleNamespace(
        get_provider_if_enabled=AsyncMock(
            return_value=SimpleNamespace(auth_callback_url="http://plugin/cb")
        )
    )
    plugin_proxy_service = SimpleNamespace(
        pass_request=AsyncMock(return_value={"email": "victim@example.com"})
    )
    http_client = SimpleNamespace(get=AsyncMock())
    service = _service(
        form_provider_service=form_provider_service,
        plugin_proxy_service=plugin_proxy_service,
        http_client=http_client,
    )

    with pytest.raises(HTTPException) as refused:
        await service.handle_backend_auth_callback(
            provider_name="google", state="s", request=None, user=signed_in
        )

    assert refused.value.status_code == 403
    # auth's /callback (which would hand out the other account) is never asked
    http_client.get.assert_not_awaited()


async def test_import_oauth_with_the_signed_in_users_own_email_proceeds():
    signed_in = User(id="u1", sub="Me@Example.com", roles=["FORM_CREATOR"])
    form_provider_service = SimpleNamespace(
        get_provider_if_enabled=AsyncMock(
            return_value=SimpleNamespace(auth_callback_url="http://plugin/cb")
        )
    )
    plugin_proxy_service = SimpleNamespace(
        pass_request=AsyncMock(return_value={"email": "me@example.com"})
    )
    http_client = SimpleNamespace(
        get=AsyncMock(return_value={"id": "u1", "sub": "Me@Example.com"})
    )
    service = _service(
        form_provider_service=form_provider_service,
        plugin_proxy_service=plugin_proxy_service,
        http_client=http_client,
        jwt_service=SimpleNamespace(encode=lambda info: "jwt"),
        crypto=SimpleNamespace(decrypt=lambda s: '{"client_referer_uri": "/x"}'),
    )

    user, state = await service.handle_backend_auth_callback(
        provider_name="google", state="s", request=None, user=signed_in
    )

    assert user.id == "u1"
    assert state.client_referer_uri == "/x"
