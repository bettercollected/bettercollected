import json
from typing import Tuple

from starlette.requests import Request

from backend.app.core.form_plugin_config import FormProvidersConfig
from backend.app.services import workspace_service
from backend.app.services.jwt_service import JwtService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.config import settings
from common.configs.crypto import Crypto
from common.models.user import User, OAuthState, UserInfo
from common.services.http_client import HttpClient

crypto = Crypto(settings.auth_settings.AES_HEX_KEY)


class AuthService:
    def __init__(
        self,
        http_client: HttpClient,
        plugin_proxy_service: PluginProxyService,
        form_providers: FormProvidersConfig,
    ):
        self.http_client = http_client
        self.plugin_proxy_service = plugin_proxy_service
        self.form_providers = form_providers

    async def get_oauth_url(self, provider_name: str, client_referer_url: str):
        provider_config = self.form_providers.get_form_provider(provider_name)
        oauth_state = OAuthState(
            client_referer_uri=client_referer_url,
        )
        state = crypto.encrypt(oauth_state.json())
        authorization_url = (
            f"{provider_config.provider_url}/{provider_name}/oauth/authorize"
        )
        response_data = await self.http_client.get(
            authorization_url, params={"state": state}, timeout=60
        )
        oauth_url = response_data.get("oauth_url")
        return oauth_url

    async def handle_backend_auth_callback(
        self, *, provider_name: str, state: str, request: Request
    ) -> Tuple[User, OAuthState]:
        provider_config = self.form_providers.get_form_provider(provider_name)
        response_data = await self.plugin_proxy_service.pass_request(
            request,
            provider_config.auth_callback_url,
        )
        user_info = UserInfo(**response_data)

        jwt_token = JwtService.encode(user_info)

        response_data = await self.http_client.get(
            settings.auth_settings.AUTH_CALLBACK_URI, params={"jwt_token": jwt_token}
        )
        user = User(**response_data)
        await workspace_service.create_workspace(user)
        decrypted_data = json.loads(crypto.decrypt(state))
        state = OAuthState(**decrypted_data)
        return user, state
