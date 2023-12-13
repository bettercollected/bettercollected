import logging
from http import HTTPStatus

import httpx
import jwt
from common.models.user import User
from starlette.requests import Request
from starlette.responses import Response

from backend.app.exceptions import HTTPException
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.services.auth_cookie_service import set_access_token_to_response
from backend.config import settings


async def get_logged_user(request: Request, response: Response) -> User:
    token = get_access_token(request)
    try:
        return get_user_from_token(token)
    # TODO : Handle specific exceptions
    except Exception as e:
        refresh_token = get_refresh_token(request)
        try:
            user = get_user_from_token(refresh_token)
            await check_if_refresh_token_is_blacklisted(refresh_token)
            async with httpx.AsyncClient() as http_client:
                user_response = await http_client.get(
                    settings.auth_settings.BASE_URL + "/auth/status",
                    params={"user_id": user.id},
                    timeout=60,
                )
                user_response = user_response.json()
                if user_response:
                    user_response["sub"] = user_response.get("email")
            set_access_token_to_response(user=User(**user_response) if user_response else user, response=response)
            return user
        except Exception as e:
            logging.error(e)
            raise HTTPException(401, "No user logged in.")


def get_api_key(request: Request, response: Response) -> str:
    if request.headers.get("api-key") != settings.temporal_settings.api_key:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content="You are not allowed to perform this action.",
        )

    return request.headers.get("api_key")


def get_user_from_token(token: str) -> User:
    jwt_response = jwt.decode(
        token,
        key=settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
    )
    user = User(**jwt_response)
    return user


async def get_user_if_logged_in(request: Request, response: Response) -> User | None:
    try:
        return await get_logged_user(request=request, response=response)
    except HTTPException:
        return None


def get_access_token(request: Request) -> str:
    access_token = request.cookies.get("Authorization")
    return access_token


def get_refresh_token(request: Request) -> str:
    refresh_token = request.cookies.get("RefreshToken")
    if not refresh_token:
        raise HTTPException(401, "RefreshToken is missing.")
    return refresh_token


async def get_logged_admin(request: Request, response: Response):
    user = await get_logged_user(request, response)
    if user.is_admin():
        return user
    else:
        raise HTTPException(403, "You are not authorized to perform this action.")


async def check_if_refresh_token_is_blacklisted(token: str):
    jwt_response = jwt.decode(
        token,
        key=settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
    )
    blacklisted_tokens = await BlackListedRefreshTokens.find_one({"token": token})
    if blacklisted_tokens:
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
