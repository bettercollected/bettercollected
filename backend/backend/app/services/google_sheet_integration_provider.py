import json

from common.configs.crypto import Crypto
from common.enums.form_provider import FormProvider
from common.services.http_client import HttpClient

from backend.app.services.base_integration_provider import BaseIntegrationProvider
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.integration_action_service import IntegrationActionService


class GoogleSheetIntegrationProvider(BaseIntegrationProvider):
    def __init__(self, form_provider_service: FormPluginProviderService,
                 crypto: Crypto,
                 http_client: HttpClient,
                 integration_action_service: IntegrationActionService
                 ):
        self.form_provider_service = form_provider_service
        self.crypto = crypto
        self.http_client = http_client
        self.integration_action_service = integration_action_service

    async def get_basic_integration_oauth_url(self, client_referer_url: str, *args, **kwargs) -> str:
        provider_url = await self.form_provider_service.get_provider_url(FormProvider.GOOGLE)
        state = {
            "client_referer_uri": client_referer_url
        }
        state = self.crypto.encrypt(json.dumps(state))
        authorization_url = f"{provider_url}/{FormProvider.GOOGLE}/oauth/integration/authorize"
        response_data = await self.http_client.get(
            authorization_url, params={"state": state}, timeout=60
        )
        oauth_url = response_data.get("oauth_url")
        return oauth_url

    async def handle_basic_integration_callback(self, code: str, state: str, form_id: str,
                                                action_id: str, *args, **kwargs) -> (
            bool, str):
        provider_url = await self.form_provider_service.get_provider_url(FormProvider.GOOGLE)
        fetch_credential_url = f"{provider_url}/{FormProvider.GOOGLE}/oauth/integration/callback"
        credential = await self.http_client.get(fetch_credential_url, params={"state": state, "code": code}, timeout=60)
        await self.integration_action_service.add_credentials_to_form_action(form_id=form_id, action_id=action_id,
                                                                             credentials=json.dumps(credential))
        return "Added credentials to form action"
