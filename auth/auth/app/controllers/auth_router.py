"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get
from starlette.requests import Request

from auth.app.container import AppContainer, container
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
