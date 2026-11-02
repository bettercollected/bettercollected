"""Session tokens carry a ``typ`` claim. Where the auth service reads a
signed-in user from a token it takes an access token only; the backend's
signed email exchange (import re-sign-in) is not a session token and a session
token is not accepted there."""

import jwt
import pytest

from auth.app.exceptions import HTTPException
from auth.app.services.auth_service import AuthService
from auth.config import settings
from common.services.jwt_service import signing_secret

USER = {"id": "5f0000000000000000000000", "sub": "staff@example.com", "roles": []}


def token(**claims) -> str:
    return jwt.encode(
        {**USER, **claims}, signing_secret(settings.AUTH_JWT_SECRET), "HS256"
    )


def test_an_access_token_gives_the_user():
    user = AuthService.get_logged_user(token(typ="access"))
    assert user.id == USER["id"] and user.sub == USER["sub"]


@pytest.mark.parametrize("typ", ["refresh", "other", "", None])
def test_nothing_but_an_access_token_gives_a_user(typ):
    with pytest.raises(jwt.InvalidTokenError):
        AuthService.get_logged_user(token(typ=typ))


def test_a_token_without_a_type_gives_no_user():
    with pytest.raises(jwt.InvalidTokenError):
        AuthService.get_logged_user(token())


def test_a_forged_token_gives_no_user():
    forged = jwt.encode({**USER, "typ": "access"}, "x" * 64, "HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        AuthService.get_logged_user(forged)


@pytest.mark.asyncio
@pytest.mark.parametrize("typ", ["access", "refresh"])
async def test_the_import_exchange_refuses_a_session_token(typ):
    claims = {"email": USER["sub"], "typ": typ}
    exchange = jwt.encode(
        claims, signing_secret(settings.AUTH_JWT_SECRET), "HS256"
    )
    with pytest.raises(HTTPException) as refused:
        await AuthService(None, None, None).handle_auth_callback(exchange, True)
    assert refused.value.status_code == 401
