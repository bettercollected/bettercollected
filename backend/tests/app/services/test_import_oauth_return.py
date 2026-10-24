"""The way back from a form provider's consent screen: the provider service's
own error reaches the user (not a generic proxy message), and the browser is
sent to a page even when the import started without a Referer."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from backend.app.constants import messages
from backend.app.exceptions import HTTPException
from backend.app.services.auth_service import AuthService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.config import settings
from common.models.user import User

SECRET_BODY_TEXT = "ya29.do-not-log-me"


def _request():
    return SimpleNamespace(
        query_params={"code": "c", "state": "s"},
        headers={},
        cookies={},
        method="GET",
        state=SimpleNamespace(),
    )


def _proxy(status: int, **body) -> PluginProxyService:
    class Client:
        async def request(self, **kwargs):
            return httpx.Response(status, **body)

    return PluginProxyService(Client())


@pytest.mark.parametrize(
    "status, message",
    [
        (417, "Invalid oauth2 grant!"),
        (403, "Google did not grant access to your forms."),
        (500, "Could not fetch oauth token!"),
    ],
)
async def test_the_plugins_status_and_message_are_passed_through(status, message):
    with pytest.raises(HTTPException) as raised:
        await _proxy(status, json=message).pass_request(_request(), "http://plugin/cb")

    assert raised.value.status_code == status
    assert raised.value.content == message


async def test_an_upstream_error_without_a_json_body_keeps_its_status():
    with pytest.raises(HTTPException) as raised:
        await _proxy(502, text="Bad Gateway").pass_request(_request(), "http://plugin/cb")

    assert raised.value.status_code == 502
    assert raised.value.content == messages.proxy_server_error


async def test_a_non_error_status_other_than_200_stays_a_proxy_error():
    with pytest.raises(HTTPException) as raised:
        await _proxy(302, text="").pass_request(_request(), "http://plugin/cb")

    assert raised.value.status_code == 500
    assert raised.value.content == messages.proxy_server_error


async def test_the_log_names_status_and_error_code_only(caplog):
    body = {"error": "invalid_grant", "detail": SECRET_BODY_TEXT}
    with caplog.at_level(logging.WARNING), pytest.raises(HTTPException):
        await _proxy(417, json=body).pass_request(
            _request(), "http://plugin/api/v1/google/oauth/callback"
        )

    logged = caplog.text
    assert "417" in logged and "invalid_grant" in logged
    assert "/api/v1/google/oauth/callback" in logged
    assert SECRET_BODY_TEXT not in logged
    assert "state" not in logged.split("callback", 1)[1]


# -- where the browser goes after the consent screen ---------------------------

CLIENT = "https://admin.example.com"


def _service(workspaces) -> AuthService:
    service = AuthService.__new__(AuthService)
    service.workspace_service = SimpleNamespace(
        get_mine_workspaces=AsyncMock(return_value=workspaces)
    )
    return service


def _ws(name, owner=True, default=False):
    return SimpleNamespace(workspace_name=name, is_owner=owner, default=default)


@pytest.fixture(autouse=True)
def _client_url(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CLIENT_URL", CLIENT + "/")


USER = User(id="u1", sub="me@example.com")


async def test_the_page_the_import_started_from_is_kept():
    url = await _service([]).import_return_url(USER, CLIENT + "/acme/dashboard/forms/create")

    assert url == CLIENT + "/acme/dashboard/forms/create"


async def test_the_picker_flag_is_added_as_a_query_parameter():
    url = await _service([]).import_return_url(
        USER, CLIENT + "/acme/dashboard/forms/create?tab=import&modal=false", modal=True
    )

    parts = urlsplit(url)
    assert parts.path == "/acme/dashboard/forms/create"
    assert parse_qs(parts.query) == {"tab": ["import"], "modal": ["true"]}


async def test_without_a_referer_the_workspace_forms_page_is_used():
    workspaces = [_ws("shared", owner=False), _ws("other"), _ws("acme", default=True)]

    url = await _service(workspaces).import_return_url(USER, None, modal=True)

    assert url == CLIENT + "/acme/dashboard/forms?modal=true"


async def test_without_a_referer_or_a_workspace_the_app_home_is_used():
    assert await _service([]).import_return_url(USER, None) == CLIENT + "/"
