"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get

from common.models.user import UserInfo
# from typeform.app.router import router
from typeform.app.services import auth_service

log = logging.getLogger(__name__)


class AuthRoutes(Routable):

    @get("/oauth/authorize")
    async def _get_oauth_url(self, state: str):
        oauth_url = await auth_service.get_oauth_url(state)
        return {"oauth_url": oauth_url}

    @get("/oauth/callback")
    async def _oauth_callback(self, code: str) -> UserInfo:
        user_info = await auth_service.handle_oauth_callback(code)
        return user_info
