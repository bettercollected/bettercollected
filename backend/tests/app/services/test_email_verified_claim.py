"""The session's ``email_verified`` claim: written into the tokens the backend
issues and recorded on the session, and handed to auth's /status on a refresh
so auth grants the config-named platform-admin role only to sessions that
proved their email."""

import http.cookies

import jwt
import pytest
from starlette.requests import Request
from starlette.responses import Response

from backend.app.container import container
from backend.app.services import session_service
from backend.app.services.user_service import get_logged_user
from backend.config import settings
from common.models.user import User
from tests.app.controllers.data import testUser


def _cookie(response: Response, key: str) -> str:
    for header in response.headers.getlist("set-cookie"):
        cookie = http.cookies.SimpleCookie(header)
        if key in cookie:
            return cookie[key].value
    raise AssertionError(f"no {key} cookie set")


def _claims(token: str) -> dict:
    return jwt.decode(token, settings.auth_settings.JWT_SECRET, algorithms=["HS256"])


async def _sign_in(verified) -> Response:
    response = Response()
    await container.session_service().start(
        User(**{**testUser.model_dump(), "email_verified": verified}), response
    )
    return response


@pytest.mark.parametrize("verified", [True, False, None])
async def test_issued_tokens_carry_the_claim(verified):
    response = await _sign_in(verified)
    for key in ("Authorization", "RefreshToken"):
        assert _claims(_cookie(response, key))["email_verified"] is (verified is True)


class FakeStatusClient:
    """Auth's /status: echoes the roles it would grant for the claim it gets."""

    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, **kwargs):
        FakeStatusClient.calls.append(params)
        roles = ["FORM_CREATOR"] + (["ADMIN"] if params["email_verified"] else [])
        body = {"id": testUser.id, "email": testUser.sub, "roles": roles}

        class Reply:
            status_code = 200

            @staticmethod
            def json():
                return body

        return Reply()


@pytest.mark.parametrize("verified", [True, False])
async def test_refresh_hands_the_claim_to_status_and_keeps_it(monkeypatch, verified):
    FakeStatusClient.calls = []
    monkeypatch.setattr(session_service.httpx, "AsyncClient", FakeStatusClient)
    refresh = _cookie(await _sign_in(verified), "RefreshToken")
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"cookie", f"Authorization=expired; RefreshToken={refresh}".encode())
            ],
        }
    )
    response = Response()

    await get_logged_user(request, response)

    (params,) = FakeStatusClient.calls
    assert params["email_verified"] is verified
    claims = _claims(_cookie(response, "Authorization"))
    assert claims["email_verified"] is verified
    assert ("ADMIN" in claims["roles"]) is verified
