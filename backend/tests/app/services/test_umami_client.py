from http import HTTPStatus
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.app.exceptions.http import HTTPException
from backend.app.services import umami_client as umami_client_module
from backend.app.services.umami_client import UmamiClient, provision_umami_website
from backend.config import settings


def _configure_umami(monkeypatch, **overrides):
    defaults = {
        "URL": "http://umami.test",
        "USERNAME": "admin",
        "PASSWORD": "secret",
        "WEBSITE_ID": "site-id",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(settings.umami_settings, key, value)


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://umami.test/api/websites/site-id/stats")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


async def test_authenticate_raises_clear_error_when_not_configured(monkeypatch):
    _configure_umami(monkeypatch, WEBSITE_ID="")
    client = UmamiClient()

    with pytest.raises(HTTPException) as exc_info:
        await client.authenticate()

    assert exc_info.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


async def test_fetch_stats_re_authenticates_once_on_401(monkeypatch):
    _configure_umami(monkeypatch)
    client = UmamiClient()
    client.token = "stale-token"

    client.client.get = AsyncMock(
        side_effect=[
            _http_status_error(401),
            httpx.Response(
                200,
                json={"pageviews": {"value": 1}},
                request=httpx.Request("GET", "http://umami.test"),
            ),
        ]
    )
    client.authenticate = AsyncMock(side_effect=lambda: setattr(client, "token", "fresh-token"))

    result = await client.fetch_stats({})

    assert result == {"pageviews": {"value": 1}}
    assert client.authenticate.await_count == 1


async def test_fetch_stats_raises_clean_error_when_retry_also_fails(monkeypatch):
    _configure_umami(monkeypatch)
    client = UmamiClient()
    client.token = "stale-token"

    client.client.get = AsyncMock(side_effect=[_http_status_error(401), _http_status_error(500)])
    client.authenticate = AsyncMock(side_effect=lambda: setattr(client, "token", "fresh-token"))

    with pytest.raises(HTTPException) as exc_info:
        await client.fetch_stats({})

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class _FakeAsyncClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient."""

    def __init__(self, post_side_effect=None, get_side_effect=None):
        self.post = AsyncMock(side_effect=post_side_effect)
        self.get = AsyncMock(side_effect=get_side_effect)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _json_response(payload, status_code=200):
    request = httpx.Request("POST", "http://umami.test/x")
    response = httpx.Response(status_code, json=payload, request=request)
    return response


async def test_provision_raises_when_no_credentials(monkeypatch):
    _configure_umami(monkeypatch, URL="", USERNAME="", PASSWORD="", WEBSITE_ID="")

    with pytest.raises(HTTPException) as exc_info:
        await provision_umami_website()

    assert exc_info.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


async def test_provision_returns_existing_website_id_by_name(monkeypatch):
    _configure_umami(monkeypatch, WEBSITE_ID="", WEBSITE_NAME="BetterCollected")
    fake_client = _FakeAsyncClient(
        post_side_effect=[_json_response({"token": "tok"})],
        get_side_effect=[
            _json_response(
                {
                    "data": [
                        {"id": "other-id", "name": "SomethingElse"},
                        {"id": "match-id", "name": "BetterCollected"},
                    ]
                }
            )
        ],
    )
    monkeypatch.setattr(umami_client_module.httpx, "AsyncClient", lambda: fake_client)

    website_id = await provision_umami_website()

    assert website_id == "match-id"
    fake_client.post.assert_awaited_once()


async def test_provision_creates_website_when_not_found(monkeypatch):
    _configure_umami(monkeypatch, WEBSITE_ID="", WEBSITE_NAME="BetterCollected")
    fake_client = _FakeAsyncClient(
        post_side_effect=[
            _json_response({"token": "tok"}),
            _json_response({"id": "new-id", "name": "BetterCollected"}),
        ],
        get_side_effect=[_json_response({"data": []})],
    )
    monkeypatch.setattr(umami_client_module.httpx, "AsyncClient", lambda: fake_client)

    website_id = await provision_umami_website()

    assert website_id == "new-id"
    assert fake_client.post.await_count == 2
