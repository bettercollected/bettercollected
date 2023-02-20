"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get
from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse

from auth.app.container import AppContainer
from auth.app.repositories import credentials_repository
from auth.app.router import router
from auth.app.services.auth_service import AuthService
from common.models.user import AuthenticationStatus, UserInfo, OAuthState, User, Credential

log = logging.getLogger(__name__)


@router(prefix="/auth")
class AuthRoutes(Routable):

    @inject
    def __init__(self, auth_service: AuthService = Provide[AppContainer.auth_service], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_service = auth_service

    @get("/status")
    async def status(self, user) -> AuthenticationStatus:
        """Define auth status endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}

    # TODO : Remove
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
    async def _auth_callback(self, jwt_token: str):
        await self.auth_service.handle_auth_callback(jwt_token)

    @get("{provider_name}/credentials")
    async def get_credentials_of_provider(self,
                                          provider_name: str,
                                          user: User =
                                          Depends(AuthService.get_logged_user)) -> Credential:
        return await self.auth_service.get_credential(email=user.sub,
                                                      provider=provider_name)
