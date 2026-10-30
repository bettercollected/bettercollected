"""Search text (a respondent's email) and receipt numbers stay out of the logs,
and the server's own access log is off."""

import logging

import pytest
from httpx import AsyncClient
from loguru import logger

import backend.__main__ as entrypoint
from backend.app.middlewares.request_privacy import (
    REDACTED,
    loggable_request,
    redact_receipts,
)
from tests.app.controllers.test_privacy_officer import (  # noqa: F401
    _cookies,
    officer,
    requested,
)

SEARCH = "someone.searched@example.test"


@pytest.fixture()
def logged(caplog):
    """Every log line of the backend: loguru's and the standard library's (not
    the test client's own httpx lines, which are not the server's log)."""
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    caplog.set_level(logging.DEBUG)
    yield lambda: "\n".join(
        lines
        + [r.getMessage() for r in caplog.records if not r.name.startswith("http")]
    )
    logger.remove(sink)


class TestRedaction:
    @pytest.mark.parametrize(
        "text",
        [
            "GET /api/v1/workspaces/w1/submissions/by-uuid/0b1c2d3e-aaaa-bbbb",
            "DELETE /api/v1/workspaces/w1/submissions/by-uuid/0b1c2d3e-aaaa-bbbb",
            "<Path: /api/v1/workspaces/w1/submissions/by-uuid/0b1c2d3e-aaaa-bbbb>",
            "TIMING: Wall: 1.0ms | CPU: 1.0ms | <Path: /x/by-uuid/0b1c2d3e-aaaa-bbbb>",
        ],
    )
    def test_the_receipt_number_is_replaced(self, text):
        out = redact_receipts(text)
        assert "0b1c2d3e" not in out
        assert f"/by-uuid/{REDACTED}" in out

    def test_other_text_is_left_alone(self):
        text = "GET /api/v1/workspaces/w1/forms/f1/submissions"
        assert redact_receipts(text) == text

    def test_the_log_line_is_method_and_path_only(self):
        line = loggable_request("GET", "/api/v1/workspaces/w1/submissions/by-uuid/abc")
        assert line == f"GET /api/v1/workspaces/w1/submissions/by-uuid/{REDACTED}"


class TestRequestLog:
    async def test_the_search_text_is_not_logged(
        self, client: AsyncClient, requested, logged
    ):
        path = "/api/v1/workspaces/{ws}/forms/{form}/submissions".format(**requested)
        response = await client.get(
            path, params={"dataOwnerIdentifier": SEARCH}, cookies=_cookies(officer)
        )
        assert response.status_code == 403  # the request itself is what is logged

        text = logged()
        assert SEARCH not in text
        assert "dataOwnerIdentifier" not in text
        # method, path and status are still there
        assert f"GET {path}" in text

    async def test_the_receipt_number_is_not_logged_by_the_read_route(
        self, client: AsyncClient, requested, logged
    ):
        stored = await _stored(requested)
        path = "/api/v1/workspaces/{ws}/submissions/by-uuid/".format(**requested)

        response = await client.get(path + stored.submission_uuid)
        assert response.status_code == 200, response.text

        text = logged()
        assert stored.submission_uuid not in text
        assert f"GET {path}{REDACTED}" in text

    async def test_the_receipt_number_is_not_logged_by_the_deletion_request_route(
        self, client: AsyncClient, requested, logged
    ):
        stored = await _stored(requested)
        path = "/api/v1/workspaces/{ws}/submissions/by-uuid/".format(**requested)

        # (the request is already filed, so this one is refused: still logged)
        await client.delete(path + stored.submission_uuid)

        text = logged()
        assert stored.submission_uuid not in text
        assert f"DELETE {path}{REDACTED}" in text

    async def test_an_unknown_receipt_number_is_not_logged_either(
        self, client: AsyncClient, requested, logged
    ):
        number = "not-a-real-receipt-number"
        path = "/api/v1/workspaces/{ws}/submissions/by-uuid/".format(**requested)

        assert (await client.get(path + number)).status_code == 404

        assert number not in logged()


async def _stored(requested):
    from backend.app.container import container

    return await container.form_response_repo().get_response(requested["response"])


def test_the_server_is_started_without_its_access_log(monkeypatch):
    """uvicorn's access log prints the whole request line, query and receipt
    number included."""
    seen = {}

    class Config:
        def __init__(self, app, **kwargs):
            seen.update(kwargs)

    class Server:
        def __init__(self, config):
            pass

        def run(self, sockets=None):
            pass

    monkeypatch.setattr(entrypoint, "get_application", lambda: object())
    monkeypatch.setattr(entrypoint.uvicorn, "Config", Config)
    monkeypatch.setattr(entrypoint.uvicorn, "Server", Server)
    monkeypatch.setattr(entrypoint, "_listening_socket", lambda port: object())
    monkeypatch.setattr(entrypoint, "log_internal_routes_setup", lambda: None)

    entrypoint.main()

    assert seen["access_log"] is False


def test_the_dev_script_turns_the_access_log_off():
    from pathlib import Path

    script = Path(entrypoint.__file__).resolve().parent.parent / "run.sh"
    assert "--no-access-log" in script.read_text()
