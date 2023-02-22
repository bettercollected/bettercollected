"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get
from dependency_injector.wiring import Provide, inject

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
    # @get("/{provider_name}/basic")
    # async def _basic_auth(self, provider_name: str, request: Request):
    #     client_referer_url = request.headers.get('referer')
    #     basic_auth_url = await self.auth_service.get_basic_auth_url(provider_name, client_referer_url)
    #     return RedirectResponse(basic_auth_url)

    @get("/callback")
    async def _auth_callback(self, jwt_token: str) -> User:
        return await self.auth_service.handle_auth_callback(jwt_token)
