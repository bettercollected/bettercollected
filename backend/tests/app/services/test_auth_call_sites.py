"""The auth service's API is internal (#766): every request to it carries the
shared key (``X-Internal-Key``), and only requests to it do.

The guard walks the backend's source: every use of
``settings.auth_settings.BASE_URL`` / ``CALLBACK_URI`` must be an argument of
a call that passes ``headers=auth_service_headers(...)``. A new call site
without it (or a URL built into a variable first) fails here."""

import ast
import http.cookies
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from starlette.requests import Request
from starlette.responses import Response

import backend
import backend.app.services.session_service as user_service
from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services import internal_auth
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.user_service import get_logged_user
from backend.config import settings
from common.models.user import User
from tests.app.controllers.data import testUser

KEY = "backend-internal-key"
AUTH_URLS = {"BASE_URL", "CALLBACK_URI"}
PACKAGE = Path(backend.__file__).parent


def _is_auth_url(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in AUTH_URLS
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "auth_settings"
    )


def _sends_the_key(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg == "headers":
            return any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "auth_service_headers"
                for n in ast.walk(keyword.value)
            )
    return False


def _auth_url_uses():
    """(file:line, sends the key) for every use of an auth service URL."""
    for path in sorted(PACKAGE.rglob("*.py")):
        if "config" in path.relative_to(PACKAGE).parts:
            continue  # where the settings are defined
        tree = ast.parse(path.read_text(), filename=str(path))
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not _is_auth_url(node):
                continue
            where = f"{path.relative_to(PACKAGE)}:{node.lineno}"
            child, parent = node, parents.get(node)
            while parent is not None and not (
                isinstance(parent, ast.Call) and child is not parent.func
            ):
                child, parent = parent, parents.get(parent)
            yield where, parent is not None and _sends_the_key(parent)


def test_every_auth_service_call_sends_the_internal_key():
    uses = list(_auth_url_uses())
    # the scan really sees the call sites (auth_service, stripe, members, ...)
    assert len(uses) >= 20, uses
    missing = [where for where, ok in uses if not ok]
    assert not missing, (
        "calls to the auth service without headers=auth_service_headers(): "
        f"{missing}"
    )


def test_the_guard_catches_a_call_without_the_key(tmp_path, monkeypatch):
    source = tmp_path / "bad.py"
    source.write_text(
        "async def f(client):\n"
        "    await client.get(settings.auth_settings.BASE_URL + '/users')\n"
        "    url = settings.auth_settings.CALLBACK_URI\n"
        "    await client.get(settings.auth_settings.BASE_URL, headers={})\n"
        "    await client.get(\n"
        "        settings.auth_settings.BASE_URL, headers=auth_service_headers()\n"
        "    )\n"
    )
    monkeypatch.setattr("tests.app.services.test_auth_call_sites.PACKAGE", tmp_path)
    found = {int(where.rsplit(":", 1)[1]): ok for where, ok in _auth_url_uses()}
    assert found == {2: False, 3: False, 4: False, 6: True}


class TestHeaders:
    def test_carries_the_key(self, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", KEY)
        assert auth_service_headers() == {"X-Internal-Key": KEY}
        assert auth_service_headers(Authorization="Bearer t") == {
            "Authorization": "Bearer t",
            "X-Internal-Key": KEY,
        }

    def test_no_header_while_unset(self, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", "")
        assert auth_service_headers() == {}

    def test_startup_check(self, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", "")
        assert internal_auth.log_if_internal_key_missing() is False
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", KEY)
        assert internal_auth.log_if_internal_key_missing() is True


class TestOtpLogin:
    async def test_send_code_sends_the_key(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", KEY)
        sent = AsyncMock(return_value={"message": "Email set to be sent"})
        with patch("common.services.http_client.HttpClient.get", sent):
            response = await client.post(
                "/api/v1/auth/creator/otp/send",
                params={"receiver_email": "someone@example.com"},
            )
        assert response.status_code == 200, response.text
        (url,), kwargs = sent.call_args
        assert url.endswith("/auth/otp/send")
        assert kwargs["headers"] == {"X-Internal-Key": KEY}

    async def test_validate_sends_the_key(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", KEY)
        sent = AsyncMock(return_value={"user": None})
        with patch("common.services.http_client.HttpClient.get", sent):
            response = await client.post(
                "/api/v1/auth/otp/validate",
                json={"email": "someone@example.com", "otp_code": "ABC-123"},
            )
        # auth found no user for the code: refused, but asked with the key
        assert response.status_code == 401, response.text
        (url,), kwargs = sent.call_args
        assert url.endswith("/auth/otp/validate")
        assert kwargs["headers"] == {"X-Internal-Key": KEY}


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
        FakeAuth.calls.append({"url": url, "headers": headers})
        status_code = FakeAuth.status_code
        body = (
            {"id": testUser.id, "email": testUser.sub, "roles": ["FORM_CREATOR"]}
            if status_code == 200
            else {"message": "Not allowed."}
        )

        class Reply:
            @staticmethod
            def json():
                return body

        Reply.status_code = status_code
        return Reply()


async def _expired_session_request() -> Request:
    signed_in = Response()
    await container.session_service().start(
        User(id=testUser.id, sub=testUser.sub, roles=["FORM_CREATOR"]), signed_in
    )
    refresh = next(
        http.cookies.SimpleCookie(h)["RefreshToken"].value
        for h in signed_in.headers.getlist("set-cookie")
        if "RefreshToken" in http.cookies.SimpleCookie(h)
    )
    cookie = f"Authorization=expired; RefreshToken={refresh}"
    return Request({"type": "http", "headers": [(b"cookie", cookie.encode())]})


class TestSessionRefresh:
    """``get_logged_user`` with an expired access token asks auth for the
    user's status with its own httpx client: it must carry the key too."""

    @pytest.fixture(autouse=True)
    def fake_auth(self, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", KEY)
        monkeypatch.setattr(user_service.httpx, "AsyncClient", FakeAuth)
        FakeAuth.calls = []
        FakeAuth.status_code = 200

    async def test_refresh_sends_the_key(self):
        response = Response()
        user = await get_logged_user(await _expired_session_request(), response)
        assert user.id == testUser.id
        (call,) = FakeAuth.calls
        assert call["url"].endswith("/auth/status")
        assert call["headers"] == {"X-Internal-Key": KEY}
        cookies = [
            http.cookies.SimpleCookie(h) for h in response.headers.getlist("set-cookie")
        ]
        assert any("Authorization" in c for c in cookies)

    @pytest.mark.parametrize("status", [403, 503])
    async def test_a_refused_refresh_is_a_clear_503(self, status):
        """A missing or mismatched key is a server misconfiguration, not a
        signed-out user: say so instead of logging them out."""
        FakeAuth.status_code = status
        with pytest.raises(HTTPException) as refused:
            await get_logged_user(await _expired_session_request(), Response())
        assert refused.value.status_code == 503


class TestDeleteUserFromAuth:
    """A retried deletion job must finish when the account is already gone."""

    class FakeSession:
        def __init__(self, status):
            self.status = status
            self.calls = []

        async def delete(self, url, headers=None, **kwargs):
            self.calls.append({"url": url, "headers": headers})
            return type("Reply", (), {"status": self.status})()

    async def _delete(self, status):
        session = self.FakeSession(status)
        with patch(
            "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
            return_value=session,
        ):
            await container.auth_service().delete_user_form_auth(testUser)
        return session

    async def test_deleted(self, monkeypatch):
        monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", "k")
        session = await self._delete(200)
        (call,) = session.calls
        assert call["url"].endswith(f"/users/{testUser.id}")
        assert call["headers"]["X-Internal-Key"] == "k"

    async def test_already_gone_counts_as_done(self):
        await self._delete(404)

    async def test_other_failures_raise(self):
        for status in (403, 500, 503):
            with pytest.raises(HTTPException):
                await self._delete(status)
