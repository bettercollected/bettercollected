from http import HTTPStatus
from typing import List

from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)
from starlette.exceptions import HTTPException

from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_NOT_FOUND
from common.enums.form_provider import FormProvider
from common.models.form_scheduler_config import AddNewFormImportJobRequest
from common.schemas.form_scheduler_config import SchedulerFormConfigDocument
from repositories.base import BaseRepository


class FormSchedulerConfigRepository(BaseRepository):
    async def list(self) -> List[SchedulerFormConfigDocument]:
        """
        Returns a list of form scheduler configs stored in the database.

        Returns:
            A list of form scheduler configs of type SchedulerFormConfigDocument.
        """
        try:
            document = await SchedulerFormConfigDocument.find_many(
                {"provider": FormProvider.GOOGLE}
            ).to_list()
            if document:
                return document
            return []
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get(
        self, form_id: str, provider: FormProvider
    ) -> SchedulerFormConfigDocument | None:
        """
        Retrieve a form scheduler config from the database.

        Args:
            form_id (str): The id of the form scheduler config to retrieve.
            provider (FormProvider): The provider of the form.

        Returns:
            SchedulerFormConfigDocument | None: The form scheduler config retrieved
                from the database.
        """
        try:
            document = await SchedulerFormConfigDocument.find_one(
                {"formId": form_id, "provider": provider}
            )
            if document:
                return document
            return None
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def add(
        self, item: AddNewFormImportJobRequest
    ) -> SchedulerFormConfigDocument:
        """
        Adds a form scheduler config in the database.

        Args:
            item (AddNewFormImportJobRequest): The added form scheduler config
                to save in the database.

        Returns:
            SchedulerFormConfigDocument: The added form scheduler config, with any
                changes made by the database.
        """
        try:
            document = SchedulerFormConfigDocument(
                email=item.email, provider=item.provider, formId=item.formId
            )
            return await document.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def update(
        self, form_id: str, item: SchedulerFormConfigDocument
    ) -> SchedulerFormConfigDocument:
        """
        Updates a form scheduler config in the database.

        Args:
            form_id (str): The id of the form scheduler config to retrieve.
            item (SchedulerFormConfigDocument): The added form scheduler config
                to save in the database.

        Returns:
            SchedulerFormConfigDocument: The added form scheduler config, with any
                changes made by the database.
        """
        try:
            provider: FormProvider | None = item.provider or FormProvider.GOOGLE
            document = await self.get(form_id, provider)
            if document:
                item.id = document.id
            return await item.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def delete(self, form_id: str, provider: FormProvider):
        """
        Deletes a form scheduler config from the database.

        Args:
            form_id (str): The id of the form scheduler config to retrieve.
            provider (FormProvider): The provider of the item.

        Returns:
            HTTPStatus.NO_CONTENT -> 204 | HTTPStatus.NOT_FOUND -> 404
        """
        try:
            document = await self.get(form_id, provider)
            if document:
                await document.delete()
                return HTTPStatus.NO_CONTENT
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail=MESSAGE_NOT_FOUND
            )
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )
