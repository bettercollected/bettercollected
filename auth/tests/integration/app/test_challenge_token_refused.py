"""The backend's second-factor challenge is signed with the same key ring as the
access token and names the same account. Its ``aud`` claim is what keeps a
decoder that ignores ``typ`` from taking it for an access token: nothing in
this service may decode a token with an audience it did not ask for."""

import time

import jwt
import pytest

from auth.app.services.auth_service import AuthService
from auth.config import settings


def challenge() -> str:
    key = settings.AUTH_JWT_SECRET.split(",")[0]
    return jwt.encode(
        {
            "typ": "mfa_challenge",
            "aud": "bc:mfa-challenge",
            "jti": "j",
            "exp": int(time.time()) + 300,
            "id": "5f0000000000000000000001",
            "sub": "victim@example.org",
            "email": "victim@example.org",
            "roles": ["FORM_CREATOR"],
        },
        key,
        algorithm="HS256",
    )


def test_get_logged_user_refuses_a_challenge():
    with pytest.raises(jwt.InvalidAudienceError):
        AuthService.get_logged_user(challenge())


@pytest.mark.asyncio
async def test_handle_auth_callback_refuses_a_challenge():
    service = AuthService.__new__(AuthService)
    with pytest.raises(jwt.InvalidAudienceError):
        await service.handle_auth_callback(challenge())
