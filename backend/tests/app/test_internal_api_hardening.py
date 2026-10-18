"""The internal API serves no docs by default and never echoes rejected input."""

import pytest
from fastapi import Body
import httpx
from pydantic import BaseModel

from backend.app.asgi import get_application
from backend.config import settings

PLANTED = "planted-secret-value-9137"
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


class _Payload(BaseModel):
    count: int


def _client(docs_enabled: bool) -> httpx.AsyncClient:
    api = settings.api_settings
    previous = api.DOCS_ENABLED
    api.DOCS_ENABLED = docs_enabled
    try:
        app = get_application()
    finally:
        api.DOCS_ENABLED = previous

    @app.post("/__validate")
    async def validate(payload: _Payload = Body(...)):
        return payload

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


def test_docs_flag_defaults_to_off():
    from backend.config.api_settings import ApiSettings

    assert ApiSettings.model_fields["DOCS_ENABLED"].default is False


@pytest.mark.parametrize("path", DOC_PATHS)
async def test_docs_are_not_served_by_default(path):
    root = settings.api_settings.ROOT_PATH
    async with _client(False) as c:
        assert (await c.get(root + path)).status_code == 404


@pytest.mark.parametrize("path", DOC_PATHS)
async def test_docs_are_served_when_enabled(path):
    root = settings.api_settings.ROOT_PATH
    async with _client(True) as c:
        assert (await c.get(root + path)).status_code == 200


async def test_the_public_api_document_stays_served():
    root = settings.api_settings.ROOT_PATH
    async with _client(False) as c:
        response = await c.get(root + "/public/v1/openapi.json")
    assert response.status_code == 200


async def test_validation_errors_do_not_echo_the_input():
    async with _client(False) as c:
        response = await c.post("/__validate", json={"count": PLANTED})

    assert response.status_code == 422
    assert PLANTED not in response.text
    detail = response.json()["detail"]
    assert detail and set(detail[0]) == {"loc", "msg", "type"}
    assert detail[0]["loc"] == ["body", "count"]
