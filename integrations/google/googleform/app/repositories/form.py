from http import HTTPStatus
from typing import List

from common.base.repo import BaseRepository
from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.enums.form_provider import FormProvider

from googleform.app.schemas.google_form import GoogleFormDocument

from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)

from starlette.exceptions import HTTPException


class FormRepository(BaseRepository):
    async def list(self) -> List[GoogleFormDocument]:
        """
        Returns a list of google forms stored in the database.

        Returns:
            A list of google form of type GoogleFormDocument.
        """
        try:
            document = await GoogleFormDocument.find_many(
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
        self, form_id: str, provider: FormProvider | str
    ) -> GoogleFormDocument | None:
        """
        Retrieve a form from the database.

        Parameters:
            form_id (str): The id of the form to retrieve.
            provider (FormProvider): The provider of the form.

        Returns:
            GoogleFormDocument | None: The form retrieved from the database.
        """
        try:
            document = await GoogleFormDocument.find_one(
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

    async def add(self, item: GoogleFormDocument) -> GoogleFormDocument:
        """
        Adds a new form in the database.

        Args:
            item (GoogleFormDocument): Form to be added to the database.

        Returns:
            GoogleFormDocument: The added form, with any changes made by the database.
        """
        # TODO: Add data saving implementation
        return item

    async def update(
        self, form_id: str, item: GoogleFormDocument
    ) -> GoogleFormDocument:
        """
        Updates a form in the database.

        Args:
            form_id (str): The id of the form to update.
            item (GoogleFormDocument): The updated form to save in the database.

        Returns:
            GoogleFormDocument: The updated form, with any changes made by the database.
        """
        try:
            provider: FormProvider | str | None = (
                item.provider if item.provider else FormProvider.GOOGLE
            )
            document = await self.get(form_id, provider)
            if document:
                item.id = document.id
            item.provider = provider
            return await item.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def delete(self, form_id: str, provider: FormProvider):
        """
        Deletes a form from the database.

        Args:
            form_id (str): The id of the form to delete.
            provider (FormProvider): The provider of the item.

        Returns:
            HTTPStatus.NO_CONTENT -> 204
        """
        # TODO: Add delete implementation
        _ = {form_id: form_id, provider: provider}
        return HTTPStatus.NO_CONTENT
