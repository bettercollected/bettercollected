from typing import Dict, Any

from backend.app.container import container
from backend.app.utils import AiohttpClient
from backend.config import settings
from common.models.user import OAuthState, User


class AuthProxyService:
    # TODO Make interface for this in common and merge with proxy service

    def __init__(self):
        self.http_client = AiohttpClient.get_aiohttp_client()

    # TODO : Separate auth from provider enabled disabled for scenario when
    # TODO : basic auth from google is allowed but import forms might not be
    async def get_oauth_url(self, provider_name: str, client_referer_url: str):
        provider_config = container.enabled_forms().get_form_provider(provider_name)
        oauth_state = OAuthState(
            backend_auth_redirect_uri=settings.BACKEND_AUTH_REDIRECT_URI,
            auth_server_redirect_uri=settings.AUTH_SERVER_REDIRECT_URI,
            client_referer_uri=client_referer_url
        )
        authorization_url = f"{provider_config.provider_url}/{provider_name}/oauth/authorize"

        response = await self.http_client.get(authorization_url,
                                              params=oauth_state.dict(exclude_none=True),
                                              timeout=60
                                              )
        oauth_url = await response.text()
        return oauth_url

    async def get_credential_of_provider(self, provider_name: str, jwt_token: str) -> Dict[str, Any]:
        provider_config = container.enabled_forms().get_form_provider(provider_name)
        response = await self.http_client.get(
            f"{provider_config.api_uri}/{provider_name}/credentials",
            params={"jwt_token": jwt_token},
        )
        return await response.json()
