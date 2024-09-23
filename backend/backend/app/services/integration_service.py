from common.configs.crypto import Crypto
from common.models.user import User
from common.services.http_client import HttpClient

from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.services.integration_provider_factory import IntegrationProviderFactory


class IntegrationService:
    def __init__(
        self,
        form_provider_service: FormPluginProviderService,
        crypto: Crypto,
        http_client: HttpClient,
        integration_action_service: IntegrationActionService,
    ):
        self.integration__provider_factory = IntegrationProviderFactory(
            form_provider_service, crypto, http_client, integration_action_service
        )

    async def get_oauth_url(
        self, integration_type: FormIntegrationType, client_referer_url: str, user: User
    ):
        return await self.integration__provider_factory.get_integration_provider(
            integration_type
        ).get_basic_integration_oauth_url(client_referer_url=client_referer_url)

    async def handle_oauth_callback(
        self,
        integration_type: FormIntegrationType,
        state: str,
        code: str,
        user: User,
        form_id: str,
        action_id: str,
    ):
        return await self.integration__provider_factory.get_integration_provider(
            integration_type
        ).handle_basic_integration_callback(
            state=state, code=code, form_id=form_id, action_id=action_id
        )
