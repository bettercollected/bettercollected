import logging

from starlette.responses import Response

from backend.app.exceptions import HTTPException
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.services.auth_cookie_service import set_access_token_to_response
from backend.config import settings

from common.models.user import User

import jwt

from starlette.requests import Request


def get_logged_user(request: Request, response: Response) -> User:
    token = get_access_token(request)
    try:
        return get_user_from_token(token)
    # TODO : Handle specific exceptions
    except Exception as e:
        refresh_token = get_refresh_token(request)
        try:
            user = get_user_from_token(refresh_token)
            check_if_refresh_token_is_blacklisted(refresh_token)
            set_access_token_to_response(user=user, response=response)
            return user
        except Exception as e:
            logging.error(e)
            raise HTTPException(401, "No user logged in.")


def get_user_from_token(token: str) -> User:
    jwt_response = jwt.decode(
        token,
        key=settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
    )
    user = User(**jwt_response)
    return user


def get_user_if_logged_in(request: Request, response: Response) -> User | None:
    try:
        return get_logged_user(request=request, response=response)
    except HTTPException:
        return None


def get_access_token(request: Request) -> str:
    access_token = request.cookies.get("Authorization")
    if not access_token:
        raise HTTPException(401, "Authorization token is missing.")
    return access_token


def get_refresh_token(request: Request) -> str:
    refresh_token = request.cookies.get("RefreshToken")
    if not refresh_token:
        raise HTTPException(401, "RefreshToken is missing.")
    return refresh_token


def get_logged_admin(request: Request, response: Response):
    user = get_logged_user(request, response)
    if user.is_admin():
        return user
    else:
        raise HTTPException(403, "You are not authorized to perform this action.")


def check_if_refresh_token_is_blacklisted(token: str):
    blacklisted_tokens = BlackListedRefreshTokens.find_sync({"token": token})
    if len(blacklisted_tokens) != 0:
        raise HTTPException(401, "Invalid JWT")


async def add_refresh_token_to_blacklist(request: Request):
    refresh_token = get_refresh_token(request)
    jwt_response = jwt.decode(
        refresh_token,
        key=settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
    )
    token_to_save = BlackListedRefreshTokens(
        token=refresh_token, expiry=jwt_response.get("exp")
    )
    await token_to_save.save()
