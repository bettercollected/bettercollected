"""Auth controller implementation."""

import logging

from classy_fastapi import Routable, get, delete, post
from common.models.user import UserInfo
from fastapi import Depends
from pydantic import EmailStr
from starlette.requests import Request

from googleform.app.containers import Container
from googleform.app.services.forms_mode import google_forms_processing_allowed

log = logging.getLogger(__name__)

# Connecting a Google account for Google Forms and handing out its stored
# credential refuse in GOOGLE_FORMS_IMPORT=readonly|off; the Sheets
# (integration) flow and deleting credentials stay.
_FORMS = Depends(google_forms_processing_allowed)


class AuthRoutes(Routable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.oauth_google_service = Container.oauth_google_service()

    @get("/oauth/authorize")
    async def _get_oauth_url(self, state: str, _forms: None = _FORMS):
        (authorization_url, state) = self.oauth_google_service.authorize(state)
        return {"oauth_url": authorization_url}

    @get("/oauth/integration/authorize")
    async def _get_integration_oauth_url(self, state: str):
        (authorization_url, state) = self.oauth_google_service.authorize(
            state, is_integration=True
        )
        return {"oauth_url": authorization_url}

    @get("/oauth/callback")
    async def _oauth_callback(
        self, request: Request, user_id: str, _forms: None = _FORMS
    ) -> UserInfo:
        user_info = await self.oauth_google_service.oauth2callback(request, user_id)
        return user_info

    @post("/oauth/integration/callback")
    def _integration_oauth_callback(self, state: str, code: str):
        response = self.oauth_google_service.handle_integration_oauth_callback(
            code=code, state=state
        )
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
    async def get_credentials(self, email: EmailStr, _forms: None = _FORMS):
        credentials = await self.oauth_google_service.get_encrypted_credential_for_user(
            email=email
        )
        return credentials
