import json
from datetime import datetime
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from pydantic.networks import EmailStr
from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)

from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.enums.form_provider import FormProvider
from common.services.crypto_service import crypto_service
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument


class OauthCredentialRepository:
    async def get(
        self,
        email: str,
        provider: FormProvider = FormProvider.GOOGLE,
        user_id: str = None,
    ) -> Oauth2CredentialDocument | None:
        """
        Get an OAuth2 credential document by email and provider.

        Args:
            email (str): The email of the user to get the credential for.
            provider (FormProvider): The provider of the form.
            user_id (str): The user_id of user to get credential for

        Returns:
            Oauth2CredentialDocument | None: An OAuth2 credential
                document if found, otherwise None.

        Raises:
            HTTPException: If there is an error connecting to the database.
        """
        try:
            document = await Oauth2CredentialDocument.find_one({"email": email})
            if document:
                document.credentials = OauthCredentialRepository.decrypt_token(
                    user_id=document.user_id, token=document.credentials
                )
                return document
            return None
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    async def add(
        self,
        email: str,
        credentials: Any,
        user_id: str,
        provider: FormProvider = FormProvider.GOOGLE,
    ) -> Oauth2CredentialDocument:
        """
        Adds an OAuth2 credential document.

        Args:
            email (str): The email of the user to update the credential.
            credentials (Any): The credential object returned after
                google authorization.
            provider (FormProvider): A form provider. Defaults to "google".
            user_id (str): The user_id of user to get credential for


        Returns:
            Oauth2CredentialDocument: The added OAuth2 credential document.

        Raises:
            HTTPException: If there is an error connecting to the database.
        """
        try:
            credentials = OauthCredentialRepository.encrypt_token(
                user_id=user_id, token=json.dumps(dict(credentials))
            )
            oauth_credential_document = Oauth2CredentialDocument(
                user_id=user_id,
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
            user_id (str): The user_id of user to get credential for

        Returns:
            Oauth2CredentialDocument: The updated OAuth2 credential document.

        Raises:
            HTTPException: If there is an error connecting to the database.
        """
        try:
            provider: FormProvider | None = item.provider or FormProvider.GOOGLE
            document = await self.get(email, provider)
            credentials = item.credentials
            if document:
                item.id = document.id
            if document.user_id:
                item.credentials = OauthCredentialRepository.encrypt_token(
                    user_id=document.user_id, token=json.dumps(dict(item.credentials))
                )
            await item.save()
            item.credentials = credentials
            return item

        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    @staticmethod
    def encrypt_token(user_id: str, token: str):
        return crypto_service.encrypt("personal", form_id=user_id, data=token)

    @staticmethod
    def decrypt_token(user_id: str, token: GoogleCredentialResponse | bytes):
        if isinstance(token, GoogleCredentialResponse):
            return token
        decrypted_token = crypto_service.decrypt(
            "personal", form_id=user_id, data=token
        )
        decrypted_token = str(decrypted_token, "utf-8")
        return GoogleCredentialResponse(**json.loads(decrypted_token))

    async def delete_oauth_credential_for_user(self, email: EmailStr, user_id: str):
        return await Oauth2CredentialDocument.find(
            {"$or": [{"email": email}, {"user_id": user_id}]}
        ).delete()
