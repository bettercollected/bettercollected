from datetime import datetime
from http import HTTPStatus
from typing import Any

from common.base.repo import AbstractOauthRepository
from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.enums.form_provider import FormProvider

from fastapi import HTTPException

from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument

from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)


class OauthCredentialRepository(AbstractOauthRepository):
    async def get(
        self, email: str, provider: FormProvider = FormProvider.GOOGLE
    ) -> Oauth2CredentialDocument | None:
        """
        Get an OAuth2 credential document by email and provider.

        Args:
            email (str): The email of the user to get the credential for.
            provider (FormProvider): The provider of the form.

        Returns:
            Oauth2CredentialDocument | None: An OAuth2 credential
                document if found, otherwise None.

        Raises:
            HTTPException: If there is an error connecting to the database.
        """
        try:
            document = await Oauth2CredentialDocument.find_one(
                {"email": email, "provider": provider}
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
        self, email: str, credentials: Any, provider: FormProvider = FormProvider.GOOGLE
    ) -> Oauth2CredentialDocument:
        """
        Adds an OAuth2 credential document.

        Args:
            email (str): The email of the user to update the credential.
            credentials (Any): The credential object returned after
                google authorization.
            provider (FormProvider): A form provider. Defaults to "google".

        Returns:
            Oauth2CredentialDocument: The added OAuth2 credential document.

        Raises:
            HTTPException: If there is an error connecting to the database.
        """
        try:
            oauth_credential_document = Oauth2CredentialDocument(
                email=email,
                provider=provider,
                credentials=credentials,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            return await oauth_credential_document.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def update(
        self, email: str, item: Oauth2CredentialDocument
    ) -> Oauth2CredentialDocument:
        """
        Update an OAuth2 credential document.

        If an OAuth2 credential document with the given email and provider
        already exists, it will be updated. Otherwise, a new document will be created.

        Args:
            email (str): The email of the user to update the credential for.
            item (Oauth2CredentialDocument): The OAuth2 credential document to update.

        Returns:
            Oauth2CredentialDocument: The updated OAuth2 credential document.

        Raises:
            HTTPException: If there is an error connecting to the database.
        """
        try:
            provider: FormProvider | None = item.provider or FormProvider.GOOGLE
            document = await self.get(email, provider)
            if document:
                item.id = document.id
            return await item.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )
