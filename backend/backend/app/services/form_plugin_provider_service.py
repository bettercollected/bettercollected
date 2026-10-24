from http import HTTPStatus
from typing import List

from common.constants import MESSAGE_NOT_FOUND, MESSAGE_PROVIDER_IS_NOT_ENABLED
from common.enums.form_provider import FormProvider
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.repositories.postgres.refdata import (
    PostgresFormPluginProviderRepository,
)
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument


class FormPluginProviderService:
    def __init__(self, form_provider_repo: PostgresFormPluginProviderRepository):
        self._form_provider_repo = form_provider_repo

    async def get_providers(self, user: User = None, get_all: bool = False):
        # a stored row of a removed integration (typeform) is not offered
        providers: List[FormProviderConfigDto] = [
            p
            for p in await self._form_provider_repo.list()
            if p.provider_name in FormProvider.list_providers()
        ]
        if (user and user.is_admin()) or get_all:
            return providers
        return [
            {"provider_name": provider.provider_name}
            for provider in providers
            if provider.enabled
        ]

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
        if user is None or not user.is_admin():
            if provider.enabled:
                return {"provider_name": provider.provider_name}
        return provider

    @staticmethod
    def _refuse_unlisted(provider_name):
        # A stored row of a removed integration (typeform) is never read: its
        # URLs point at a service that no longer runs, and a leftover container
        # there must not receive the user's request.
        if (
            getattr(provider_name, "value", provider_name)
            not in FormProvider.list_providers()
        ):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )

    async def get_provider_if_enabled(self, provider_name):
        self._refuse_unlisted(provider_name)
        provider = await self._form_provider_repo.get(provider_name)
        if not provider:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
        if not provider.enabled:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=MESSAGE_PROVIDER_IS_NOT_ENABLED.format(
                    provider=provider.provider_name
                ),
            )
        return provider

    async def get_provider_url(self, provider_name) -> str:
        self._refuse_unlisted(provider_name)
        provider = await self._form_provider_repo.get_provider_url(provider_name)
        return provider.provider_url
