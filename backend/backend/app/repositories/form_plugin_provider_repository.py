from http import HTTPStatus
from typing import List

from pydantic import BaseModel
from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)

from backend.app.exceptions import HTTPException
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from common.base.repo import BaseRepository
from common.constants import MESSAGE_DATABASE_EXCEPTION


class FormPluginProviderRepository(BaseRepository):
    async def list(self) -> List[FormProviderConfigDto]:
        try:
            document = await FormPluginConfigDocument.find_many().to_list()
            if document:
                return [
                    FormProviderConfigDto(**provider.dict()) for provider in document
                ]
            return []
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    # noinspection PyMethodOverriding
    async def get(self, provider_name: str) -> FormPluginConfigDocument | None:
        try:
            document = await FormPluginConfigDocument.find_one(
                {"provider_name": provider_name}
            )
            if document:
                return document
            return None
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    class ProviderUrlProject(BaseModel):
        provider_url: str

    async def get_provider_url(self, provider_name) -> ProviderUrlProject:
        return await FormPluginConfigDocument.find_one(
            {"provider_name": provider_name}, projection_model=self.ProviderUrlProject
        )

    async def add(self, item: FormPluginConfigDocument) -> FormPluginConfigDocument:
        try:
            return await item.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def update(
        self, provider_name: str, item: FormPluginConfigDocument
    ) -> FormPluginConfigDocument:
        try:
            document = await self.get(provider_name)
            if document:
                item.id = document.id
            return await item.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def delete(self, provider_name: str, provider: FormPluginConfigDocument):
        pass
