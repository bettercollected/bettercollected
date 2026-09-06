from http import HTTPStatus

from common.configs.crypto import Crypto
from common.services.http_client import HttpClient

from backend.app.exceptions import HTTPException
from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.google_sheet_integration_provider import GoogleSheetIntegrationProvider
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.repositories.form_repository import FormRepository


class IntegrationProviderFactory:
    def __init__(self, form_provider_service: FormPluginProviderService,
                 crypto: Crypto,
                 http_client: HttpClient, integration_action_service: IntegrationActionService,
                 form_repo: FormRepository) -> None:
        self.google_integration_provider = GoogleSheetIntegrationProvider(form_provider_service, crypto, http_client,
                                                                          integration_action_service, form_repo)

    def get_integration_provider(self, integration_type: FormIntegrationType):
        if integration_type == FormIntegrationType.GOOGLE_SHEET:
            return self.google_integration_provider
        raise HTTPException(HTTPStatus.NOT_IMPLEMENTED, "Integration provider not available")
