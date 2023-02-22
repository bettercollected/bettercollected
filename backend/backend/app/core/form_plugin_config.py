from typing import List, Optional, Dict, Any

from backend.app.exceptions import HTTPException
from backend.app.constants import messages
from backend.app.exceptions.provider_config_exception import (
    MultipleProviderConfigException,
)
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.services.form_plugin_provider_service import FormPluginProviderService


class FormProvidersConfig:
    # Holds all the form providers that are present
    form_providers: List[FormProviderConfigDto]
    # Holds only those form providers which are enabled
    current_form_providers: List[FormProviderConfigDto]

    def __init__(self, form_provider_service: FormPluginProviderService):
        self._form_provider_service = form_provider_service
        self.form_providers = []
        self.current_form_providers = [f for f in self.form_providers if f.enabled]

    async def _get_providers(self):
        return await self._form_provider_service.get_providers(True)

    def get_form_provider(self, provider_name: str) -> FormProviderConfigDto:
        form_provider = list(
            filter(
                lambda f: f.provider_name == provider_name, self.current_form_providers
            )
        )
        if not form_provider:
            raise HTTPException(400, messages.provider_is_not_enabled_error)
        if len(form_provider) > 1:
            raise MultipleProviderConfigException(
                500, messages.multiple_provider_config_found
            )
        return form_provider[0]
