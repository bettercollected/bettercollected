from http import HTTPStatus
from typing import List

from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)
from starlette.exceptions import HTTPException

from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.enums.form_provider import FormProvider
from repositories.base import BaseRepository
from schemas.google_form_response import GoogleFormResponseDocument


class FormResponseRepository(BaseRepository):
    async def list(self) -> List[GoogleFormResponseDocument]:
        """
        Returns a list of google form responses stored in the database.

        Returns:
            A list of google form responses of type GoogleFormResponseDocument.
        """
        try:
            document = await GoogleFormResponseDocument.find_many(
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

    @staticmethod
    async def list_form_responses(form_id: str) -> List[GoogleFormResponseDocument]:
        """
        Returns a list of google form responses of specific formId
        stored in the database.

        Returns:
            A list of google form responses of specific formId of
            type GoogleFormResponseDocument.
        """
        try:
            return await GoogleFormResponseDocument.find(
                {"formId": form_id, "provider": FormProvider.GOOGLE}
            ).to_list()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get(
        self, response_id: str, provider: FormProvider | str
    ) -> GoogleFormResponseDocument | None:
        """
        Retrieve a form response from the database.

        Parameters:
            response_id (str): The id of the form response to retrieve.
            provider (FormProvider): The provider of the form.

        Returns:
            GoogleFormResponseDocument | None: The form response retrieved
                from the database.
        """
        try:
            document = await GoogleFormResponseDocument.find_one(
                {"responseId": response_id, "provider": provider}
            )
            if document:
                return document
            return None
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def add(self, item: GoogleFormResponseDocument) -> GoogleFormResponseDocument:
        """
        Adds a form response in the database.

        Args:
            item (GoogleFormResponseDocument): The added form to save
                in the database.

        Returns:
            GoogleFormResponseDocument: The added form, with any
                changes made by the database.
        """
        try:
            document = GoogleFormResponseDocument(**item.dict())
            return await document.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def update(
        self, response_id: str, item: GoogleFormResponseDocument
    ) -> GoogleFormResponseDocument:
        """
        Updates a form response in the database.

        Args:
            response_id (str): The id of the form response to update.
            item (GoogleFormResponseDocument): The updated form to save
                in the database.

        Returns:
            GoogleFormResponseDocument: The updated form, with any
                changes made by the database.
        """
        try:
            provider: FormProvider | str | None = (
                item.provider if item.provider else FormProvider.GOOGLE
            )
            document = await self.get(response_id, provider)
            if document:
                item.id = document.id
            return await item.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def delete(
        self, response_id: str, provider: FormProvider = FormProvider.GOOGLE
    ):
        """
        Deletes a form response from the database.

        Args:
            response_id (str): The id of the form response to delete.
            provider (FormProvider): The provider of the item.

        Returns:
            HTTPStatus.NO_CONTENT -> 204 | HTTPStatus.NOT_FOUND -> 404
        """
        try:
            document = await self.get(response_id, provider)
            if document:
                await document.delete()
                return HTTPStatus.NO_CONTENT
            return HTTPStatus.NOT_FOUND
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )
