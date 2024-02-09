"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get, delete
from common.models.user import UserInfo
from pydantic import EmailStr
from starlette.requests import Request

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

    @get("/oauth/integration/authorize")
    async def _get_integration_oauth_url(self, state: str):
        (authorization_url, state) = self.oauth_google_service.authorize(state, is_integration=True)
        return {"oauth_url": authorization_url}

    @get("/oauth/callback")
    async def _oauth_callback(self, request: Request, user_id: str) -> UserInfo:
        user_info = await self.oauth_google_service.oauth2callback(request, user_id)
        return user_info

    @get("/oauth/integration/callback")
    def _integration_oauth_callback(self, state: str, code: str):
        response = self.oauth_google_service.handle_integration_oauth_callback(code=code, state=state)
        return response

    @delete("/oauth/credentials")
    async def _delete_oauth_credentials(
            self, email: EmailStr = None, user_id: str = None
    ):
        await self.oauth_google_service.delete_oauth_credentials_for_user(
            email=email, user_id=user_id
        )
        return "Credentials Deleted Successfully"

    @get("/credentials")
    async def get_credentials(self, email: EmailStr):
        credentials = await self.oauth_google_service.get_encrypted_credential_for_user(
            email=email
        )
        return credentials
