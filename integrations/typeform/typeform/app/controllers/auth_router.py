"""Auth controller implementation."""
import logging

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, delete
from pydantic import EmailStr
from starlette.requests import Request

from common.models.user import UserInfo
from typeform.app.services import auth_service

log = logging.getLogger(__name__)


class AuthRoutes(Routable):
    @get("/oauth/authorize")
    async def _get_oauth_url(self, state: str):
        oauth_url = await auth_service.get_oauth_url(state)
        return {"oauth_url": oauth_url}

    @get("/oauth/callback")
    async def _oauth_callback(
        self, code: str, request: Request, user_id: str = None
    ) -> UserInfo:
        user_info = await auth_service.handle_oauth_callback(code, user_id)
        return user_info

    @delete("/oauth/credentials")
    async def _delete_oauth_credentials(
        self, email: EmailStr = None, user_id: PydanticObjectId = None
    ):
        result = await auth_service.delete_oauth_credentials_for_user(
            email=email, user_id=user_id
        )
        return "Credentials Deleted Successfully"
