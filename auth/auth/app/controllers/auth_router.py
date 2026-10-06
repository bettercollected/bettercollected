"""Auth controller implementation."""

import logging
from typing import Optional

from beanie import PydanticObjectId

from auth.app.container import container
from auth.app.controllers.internal_key import INTERNAL_ONLY
from auth.app.router import router
from auth.app.services.auth_service import AuthService

from classy_fastapi import Routable, get

from common.models.user import (
    User,
)

from fastapi import Query
from pydantic import EmailStr

from starlette.background import BackgroundTasks
from starlette.requests import Request

log = logging.getLogger(__name__)


@router(prefix="/auth", dependencies=INTERNAL_ONLY)
class AuthRoutes(Routable):
    def __init__(
        self, auth_service: AuthService = container.auth_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.auth_service = auth_service

    @get("/status")
    async def _get_user_status(
        self, user_id: PydanticObjectId, email_verified: bool = False
    ):
        return await self.auth_service.get_user_status(user_id, email_verified)

    @get("/otp/send")
    async def _send_otp_to_email(
        self,
        receiver_email: EmailStr,
        creator: bool,
        background_tasks: BackgroundTasks,
        # shown in the mail body only, never in From or the subject (#761);
        # the image only from this instance's storage (MAIL_IMAGE_URL_PREFIXES)
        workspace_title: Optional[str] = Query(None, max_length=1000),
        workspace_profile_image: Optional[str] = Query(None, max_length=2000),
    ):
        background_tasks.add_task(
            self.auth_service.send_otp_to_mail,
            receiver_mail=receiver_email,
            workspace_title=workspace_title,
            workspace_profile_image=workspace_profile_image,
            creator=creator,
        )
        return {"message": "Email set to be sent"}

    @get("/otp/validate")
    async def _validate_otp(self, email: EmailStr, otp_code: str):
        user = await self.auth_service.validate_otp(email, otp_code)
        return {"user": user}

    @get("/{provider_name}/basic")
    async def _basic_auth(
        self,
        provider_name: str,
        client_referer_url,
        creator: bool = False,
        prospective_pro_user: bool = False,
    ):
        basic_auth_url = await self.auth_service.get_basic_auth_url(
            provider_name, client_referer_url, creator, prospective_pro_user
        )
        return basic_auth_url

    @get("/{provider}/basic/callback")
    async def _basic_auth_callback(
        self, provider: str, code: str, state: str, request: Request
    ):
        basic_auth_url = await self.auth_service.basic_auth_callback(
            provider, code, state, request=request
        )
        return basic_auth_url

    @get("/callback")
    async def _auth_callback(
        self, jwt_token: str, email_verified: bool = False
    ) -> User:
        """``email_verified``: the signed-in session's claim; the backend only
        exchanges that session's own email here (#763)."""
        return await self.auth_service.handle_auth_callback(jwt_token, email_verified)
