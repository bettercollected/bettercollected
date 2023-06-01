"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get
from starlette.requests import Request

from common.models.user import UserInfo
from googleform.app.containers import Container

log = logging.getLogger(__name__)


class AuthRoutes(Routable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.oauth_google_service = Container.oauth_google_service()

    @get("/oauth/authorize")
    async def _get_oauth_url(self, state: str):
        (authorization_url, state) = self.oauth_google_service.authorize(state)
        return {"oauth_url": authorization_url}

    @get("/oauth/callback")
    async def _oauth_callback(self, request: Request, user_id: str) -> UserInfo:
        user_info = await self.oauth_google_service.oauth2callback(request, user_id)
        return user_info
