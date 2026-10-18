"""The internal API serves no docs by default and never echoes rejected input."""

import pytest
from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import BaseModel

from auth.app.asgi import get_application
from auth.config import settings
from auth.config.application import Application

PLANTED = "planted-secret-value-9137"
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


class _Payload(BaseModel):
    count: int


def _client(docs_enabled: bool) -> TestClient:
    previous = settings.API_DOCS_ENABLED
    settings.API_DOCS_ENABLED = docs_enabled
    try:
        app = get_application()
    finally:
        settings.API_DOCS_ENABLED = previous

    @app.post("/__validate")
    async def validate(payload: _Payload = Body(...)):
        return payload

    return TestClient(app, raise_server_exceptions=False)


def test_docs_flag_defaults_to_off():
    assert Application.model_fields["API_DOCS_ENABLED"].default is False


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_are_not_served_by_default(path):
    assert _client(False).get(settings.API_ROOT_PATH + path).status_code == 404


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_are_served_when_enabled(path):
    assert _client(True).get(settings.API_ROOT_PATH + path).status_code == 200


def test_validation_errors_do_not_echo_the_input():
    response = _client(False).post("/__validate", json={"count": PLANTED})

    assert response.status_code == 422
    assert PLANTED not in response.text
    detail = response.json()["detail"]
    assert detail and set(detail[0]) == {"loc", "msg", "type"}
    assert detail[0]["loc"] == ["body", "count"]
