"""Auth controller implementation."""
import json
import logging

from classy_fastapi import Routable, get
from fastapi import Depends

from common.models.user import OAuthState

# from typeform.app.router import router
from typeform.app.services import auth_service

log = logging.getLogger(__name__)


# @router(prefix="/typeform")
class AuthRoutes(Routable):

    # @inject
    # def __init__(self, auth_service: Provide[AppContainer.auth_service], *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.auth_service = auth_service

    @get("/oauth/authorize")
    async def _get_oauth_url(self, oauth_state: OAuthState = Depends()) -> str:
        oauth_url = await auth_service.get_oauth_url(oauth_state=oauth_state)
        return oauth_url

    @get("oauth/callback")
    async def _oauth_callback(self, code: str, state: str):
        await auth_service.handle_oauth_callback(code, state=state)
