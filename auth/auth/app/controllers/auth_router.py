"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get
from pydantic import EmailStr
from starlette.background import BackgroundTasks
from starlette.requests import Request

from auth.app.container import container
from auth.app.router import router
from auth.app.services.auth_service import AuthService
from common.models.user import (
    User,
)

log = logging.getLogger(__name__)


@router(prefix="/auth")
class AuthRoutes(Routable):
    def __init__(
            self, auth_service: AuthService = container.auth_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.auth_service = auth_service

    # TODO : Refactor for basic auth and oauth might be required or not
    # @get("/{provider_name}/oauth")
    # async def _oauth_provider(self,
    #                           provider_name: str,
    #                           oauth_state: OAuthState):
    #     oauth_url = await self.auth_service.get_oauth_url(provider_name, oauth_state)
    #     return oauth_url
    #

    @get("/otp/send")
    async def _send_otp_to_email(
            self,
            receiver_email: EmailStr,
            workspace_title: str,
            background_tasks: BackgroundTasks,
    ):
        background_tasks.add_task(
            self.auth_service.send_code_to_user_for_workspace_sync,
            receiver_email,
            workspace_title,
        )

        # await self.auth_service.send_otp_to_mail(receiver_mail=receiver_email, workspace_title=workspace_title)
        return "Email set to be sent"

    @get("/otp/validate")
    async def _validate_otp(self, email: EmailStr, otp_code: str):
        user = await self.auth_service.validate_otp(email, otp_code)
        return {
            "user": user
        }

    @get("/{provider_name}/basic")
    async def _basic_auth(self, provider_name: str, client_referer_url):
        basic_auth_url = await self.auth_service.get_basic_auth_url(
            provider_name, client_referer_url
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
    async def _auth_callback(self, jwt_token: str) -> User:
        return await self.auth_service.handle_auth_callback(jwt_token)
