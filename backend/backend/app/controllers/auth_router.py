"""Auth controller implementation."""
import logging

import jwt
from classy_fastapi import Routable, get
from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from backend.app.container import AppContainer, container
from backend.app.router import router
from backend.app.services import backend_auth_service
from backend.app.services.auth_cookie_service import set_tokens_to_response
from backend.app.services.auth_proxy_service import AuthProxyService
from backend.app.services.user_service import get_logged_user
from backend.config import settings
from common.models.user import AuthenticationStatus, OAuthState, User

log = logging.getLogger(__name__)


# TODO merge this to plugin interface
# TODO Extract out separate interface for oauth and use it
@router(prefix="/auth", tags=["Auth"])
class AuthRoutes(Routable):

    def __init__(self, auth_service=container.auth_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_service = auth_service

    @get("/status")
    async def status(
        self, user: User = Depends(get_logged_user)
    ) -> AuthenticationStatus:
        """Define auth status endpoint."""
        # Implement endpoint logic here.
        return AuthenticationStatus(user=user)

    # TODO : Merge with plugin proxy currently it is handled for typeform only
    @get("/{provider_name}/oauth")
    async def _oauth_provider(self, provider_name: str, request: Request):
        client_referer_url = request.headers.get("referer")
        oauth_url = await AuthProxyService().get_oauth_url(
            provider_name, client_referer_url
        )
        return RedirectResponse(oauth_url)

    # @get("/{provider}/basic")
    # async def _basic_auth(self, provider_name: str, request: Request):
    #     client_referer_url = request.headers.get('referer')
    #     basic_auth_url = await self.auth_service.get_basic_auth_url(provider_name, client_referer_url)
    #     return RedirectResponse(basic_auth_url)

    @get("/{provider_name}/oauth/callback")
    async def _auth_callback(self, request: Request, response: Response):
        user, state = await self.auth_service.handle_backend_auth_callback(request)
        set_tokens_to_response(user, response)
        return RedirectResponse(state.client_referer_uri)
