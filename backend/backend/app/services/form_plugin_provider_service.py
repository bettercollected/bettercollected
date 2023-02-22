from http import HTTPStatus
from typing import List

from backend.app.core.form_plugin_config import FormProvider
from backend.app.exceptions import HTTPException
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from common.constants import MESSAGE_NOT_FOUND


class FormPluginProviderService:
    def __init__(self, form_provider_repo: FormPluginProviderRepository):
        self._form_provider_repo = form_provider_repo

    async def get_providers(self, is_admin: bool):
        providers: List[FormProvider] = await self._form_provider_repo.list()
        if is_admin:
            return providers
        return [provider.provider_name for provider in providers if provider.enabled]

    async def add_provider(self, provider: FormProvider):
        return await self._form_provider_repo.add(
            FormPluginConfigDocument(**provider.dict())
        )

    async def update_provider(self, provider_name: str, provider: FormProvider):
        return await self._form_provider_repo.update(
            provider_name, FormPluginConfigDocument(**provider.dict())
        )

    async def get_provider(self, provider_name: str, is_admin: bool):
        provider = await self._form_provider_repo.get(provider_name)
        if is_admin:
            return provider
        if provider:
            return provider.provider_name
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)
