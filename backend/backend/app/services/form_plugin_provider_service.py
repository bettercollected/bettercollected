from http import HTTPStatus
from typing import List

from common.constants import MESSAGE_NOT_FOUND, MESSAGE_PROVIDER_IS_NOT_ENABLED
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.services.google_forms_mode import (
    google_forms_import_mode,
    google_service_enabled,
    is_google,
    refuse_google_service_call,
)


def _listed(provider) -> bool:
    """In ``GOOGLE_FORMS_IMPORT=off`` Google Forms is not offered at all."""
    return google_service_enabled() or not is_google(provider.provider_name)


class FormPluginProviderService:
    def __init__(self, form_provider_repo: FormPluginProviderRepository):
        self._form_provider_repo = form_provider_repo

    async def get_providers(self, user: User = None, get_all: bool = False):
        providers: List[FormProviderConfigDto] = await self._form_provider_repo.list()
        if get_all:
            return providers
        if user and user.is_admin():
            return [provider for provider in providers if _listed(provider)]
        return [
            self._public_view(provider)
            for provider in providers
            if provider.enabled and _listed(provider)
        ]

    @staticmethod
    def _public_view(provider) -> dict:
        view = {"provider_name": provider.provider_name}
        if is_google(provider.provider_name):
            # on | readonly (an "off" provider is not listed): the webapp
            # offers imports only when "on"
            view["import_mode"] = google_forms_import_mode().value
        return view

    async def add_provider(self, provider: FormProviderConfigDto):
        return await self._form_provider_repo.add(
            FormPluginConfigDocument(**provider.model_dump(mode='json'))
        )

    async def update_provider(
        self, provider_name: str, provider: FormProviderConfigDto
    ):
        return await self._form_provider_repo.update(
            provider_name, FormPluginConfigDocument(**provider.model_dump(mode='json'))
        )

    async def get_provider(self, provider_name: str, user: User = None):
        provider = await self._form_provider_repo.get(provider_name)
        if not provider:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
        refuse_google_service_call(provider.provider_name)
        if user is None or not user.is_admin():
            if provider.enabled:
                return self._public_view(provider)
        return provider

    async def get_provider_if_enabled(self, provider_name):
        provider = await self._form_provider_repo.get(provider_name)
        if not provider:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
        refuse_google_service_call(provider.provider_name)
        if not provider.enabled:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=MESSAGE_PROVIDER_IS_NOT_ENABLED.format(
                    provider=provider.provider_name
                ),
            )
        return provider

    async def get_provider_url(self, provider_name) -> str:
        # every call to a provider service starts here: in
        # GOOGLE_FORMS_IMPORT=off nothing reaches the Google Forms service
        refuse_google_service_call(provider_name)
        provider = await self._form_provider_repo.get_provider_url(provider_name)
        return provider.provider_url
