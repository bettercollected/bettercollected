"""Auth controller implementation."""
import logging
from typing import Optional

from classy_fastapi import Routable, get, post
from fastapi import Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from backend.app.container import container
from backend.app.models.generic_models import (
    GenericResponseModel,
    generate_generic_pageable_response,
)
from backend.app.router import router
from backend.app.services.auth_cookie_service import (
    set_tokens_to_response,
    delete_token_cookie,
)
from backend.app.services.user_service import get_logged_user
from common.models.user import AuthenticationStatus, User

log = logging.getLogger(__name__)


# TODO merge this to plugin interface
# TODO Extract out separate interface for oauth and use it
@router(prefix="/auth", tags=["Auth"])
class AuthRoutes(Routable):
    def __init__(self, auth_service=container.auth_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_service = auth_service

    @get("/status")
    async def status(self, user: User = Depends(get_logged_user)):
        return GenericResponseModel[AuthenticationStatus](
            payload=generate_generic_pageable_response(
                data=AuthenticationStatus(user=user)
            )
        )

    # TODO : Merge with plugin proxy currently it is handled for typeform only
    @get("/{provider_name}/oauth")
    async def _oauth_provider(
        self, provider_name: str, request: Request, creator: Optional[str] = True
    ):
        client_referer_url = request.headers.get("referer")
        oauth_url = await self.auth_service.get_oauth_url(
            provider_name, client_referer_url
        )
        return RedirectResponse(oauth_url)

    @get("/{provider_name}/oauth/callback")
    async def _auth_callback(self, provider_name: str, state: str, request: Request):
        user, state_data = await self.auth_service.handle_backend_auth_callback(
            provider_name=provider_name, state=state, request=request
        )
        response = RedirectResponse(state_data.client_referer_uri)
        set_tokens_to_response(user, response)
        if state_data.client_referer_uri:
            return response
        return {"message": "Token saved successfully."}

    @get("/{provider}/basic")
    async def _basic_auth(self, provider: str, request: Request):
        client_referer_url = request.headers.get("referer")
        basic_auth_url = await self.auth_service.get_basic_auth_url(
            provider, client_referer_url
        )
        return RedirectResponse(basic_auth_url)

    @get("/{provider}/basic/callback")
    async def _basic_auth_callback(self, provider: str, code: str, state: str):
        user, client_referer_url = await self.auth_service.basic_auth_callback(
            provider, code, state
        )
        response = RedirectResponse(client_referer_url)
        if user:
            set_tokens_to_response(User(**user), response)
        return response

    @get("/logout")
    async def logout(self, response: Response):
        delete_token_cookie(response=response)
        return "Logged out successfully!!!"
