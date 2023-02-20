from backend.app.core.form_plugin_config import FormProvider
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument


class FormPluginProviderService:
    def __init__(self, form_provider_repo: FormPluginProviderRepository):
        self._form_provider_repo = form_provider_repo

    async def get_providers(self):
        return await self._form_provider_repo.list()

    async def add_provider(self, provider: FormProvider):
        return await self._form_provider_repo.add(FormPluginConfigDocument(**provider.dict()))

    async def update_provider(self, provider_name: str, provider: FormProvider):
        return await self._form_provider_repo.update(provider_name, FormPluginConfigDocument(**provider.dict()))

    async def get_provider(self, provider_name: str):
        return await self._form_provider_repo.get(provider_name)
