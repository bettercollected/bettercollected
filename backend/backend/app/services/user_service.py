import logging
from http import HTTPStatus

import jwt
from fastapi import Depends
from common.models.user import User
from starlette.requests import Request
from starlette.responses import Response

from backend.app.exceptions import HTTPException
from backend.app.services.auth_cookie_service import delete_token_cookie
from backend.app.services.session_service import (
    AuthServiceUnavailable,
    SessionEnded,
    user_from_access_token,
)
from backend.config import settings


async def get_logged_user(request: Request, response: Response) -> User:
    """The signed-in user. A live access token is trusted as is; otherwise the
    session is refreshed (see ``session_service``), which fails with 401 and
    cleared cookies when the session was revoked or has ended."""
    user = user_from_access_token(get_access_token(request))
    if user is not None:
        return user
    from backend.app.container import (
        container,
    )  # at call time: container imports this module

    try:
        return await container.session_service().refresh(
            request, response, rotate=False
        )
    except HTTPException:
        raise
    except AuthServiceUnavailable as e:
        logging.error(
            f"Session refresh: the auth service answered {e.status_code}; "
            "check AUTH_INTERNAL_NOTIFY_KEY on the backend and auth services"
        )
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "Sign-in is temporarily unavailable.",
        )
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


def get_user_from_token(token: str, *, verify_exp: bool = True) -> User:
    """The user a token this backend signed names (any token type, no session
    check): for server-side jobs holding a user's stored tokens."""
    jwt_response = jwt.decode(
        token,
        key=settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_exp": verify_exp},
    )
    user = User(**jwt_response)
    return user


async def get_user_if_logged_in(request: Request, response: Response) -> User | None:
    try:
        return await get_logged_user(request=request, response=response)
    except SessionEnded:
        delete_token_cookie(response)
        return None
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


def get_user_for_internal_job(
    request: Request, response: Response, api_key: str = Depends(get_api_key)
) -> User:
    """For server-side jobs (the user-deletion workflow) that call with the
    temporal API key and the user's tokens stored when the job was queued: the
    signature is checked, not the expiry or the session, which the job may
    outlive (the deletion request itself revokes the user's sessions)."""
    try:
        return get_user_from_token(get_access_token(request), verify_exp=False)
    except Exception:
        raise HTTPException(401, "No user logged in.")
