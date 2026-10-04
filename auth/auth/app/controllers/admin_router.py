"""Platform-admin endpoints (``ADMIN`` in the token's roles, not workspace
admins). The backend calls them with the requesting admin's access token and,
like every internal route, the internal key."""

import datetime as dt
from http import HTTPStatus
from typing import Optional

from classy_fastapi import Routable, get
from fastapi import Depends, Header, Query

from auth.app.container import container
from auth.app.controllers.internal_key import INTERNAL_ONLY
from auth.app.exceptions import HTTPException
from auth.app.router import router
from auth.app.services.auth_service import AuthService
from auth.app.services.user_service import UserService
from common.models.user import User


def get_bearer_user(authorization: Optional[str] = Header(None)) -> User:
    """The caller from a ``Bearer`` token; 401 without a valid one."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Authorization token is missing.")
    try:
        return AuthService.get_logged_user(token)
    except Exception:  # noqa: BLE001 — expired, forged or malformed alike
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid authorization token.")


def get_platform_admin(authorization: Optional[str] = Header(None)) -> User:
    """The caller from a ``Bearer`` token; 401 without a valid one, 403 unless
    it carries the ADMIN role."""
    user = get_bearer_user(authorization)
    if not user.is_admin():
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "You are not authorized to perform this action."
        )
    return user


@router(prefix="/admin", tags=["Platform admin"], dependencies=INTERNAL_ONLY)
class AdminRouter(Routable):
    def __init__(self, user_service=container.user_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_service: UserService = user_service

    @get("/metrics")
    async def get_user_metrics(
        self,
        first_week: dt.date = Query(...),
        weeks: int = Query(12, ge=1, le=52),
        _: User = Depends(get_platform_admin),
    ):
        return await self.user_service.get_platform_user_metrics(first_week, weeks)
