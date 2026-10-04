import hmac
import json
import logging
from http import HTTPStatus

from fastapi import Depends
from common.models.user import User
from starlette.requests import Request
from starlette.responses import Response

from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.user_tokens import UserDeletion
from backend.app.services.auth_cookie_service import delete_token_cookie
from backend.app.services.internal_job_key import require_job_api_key
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
    expected = require_job_api_key()  # 503 while not configured
    given = (request.headers.get("api-key") or "").encode()
    if not hmac.compare_digest(given, expected.encode()):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content="You are not allowed to perform this action.",
        )

    return request.headers.get("api_key")


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


USER_DELETION_HEADER = "X-User-Deletion"


def user_for_deletion(encrypted: str) -> User:
    """Whose account a deletion job deletes: the :class:`UserDeletion` the
    backend encrypted when the deletion was requested (authenticated
    encryption with the backend's key, so nobody else can mint one). Requests
    queued before this format (stored tokens) are refused."""
    from backend.app.container import (
        container,
    )  # at call time: container imports this module

    data = json.loads(container.crypto().decrypt(encrypted))
    deletion = UserDeletion(user_id=data["user_id"], email=data["email"])
    if not deletion.user_id or not deletion.email:
        raise ValueError("incomplete deletion request")
    return User(id=deletion.user_id, sub=deletion.email)


def get_user_to_delete(
    request: Request, response: Response, api_key: str = Depends(get_api_key)
) -> User:
    """For the Temporal deletion workflow: the API key, plus the encrypted
    deletion request it was started with in ``X-User-Deletion``."""
    try:
        return user_for_deletion(request.headers.get(USER_DELETION_HEADER) or "")
    except Exception:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid deletion request.")
