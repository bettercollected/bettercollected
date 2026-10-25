import json
import logging
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
from common.db import WriteResult, write_op
from common.enums.form_provider import FormProvider
from common.services.crypto_service import crypto_service
from common.clock import utcnow
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument

log = logging.getLogger(__name__)


def update_key(
    stored: Oauth2CredentialDocument | None, item: Oauth2CredentialDocument
) -> str | None:
    """The user id a credential update is encrypted with, or None when nothing
    may be written.

    The encryption key is derived from the user id, so without one the tokens
    could only be stored in plain text: such an update writes nothing. The
    stored row's user id wins; the caller's (the OAuth callback knows the
    signed-in user) gives a legacy row connected by an older version its user
    id. Without a stored row there is nothing to update. Logs the row id only.
    """
    if stored is None:
        log.warning("google credential update skipped: no stored credential")
        return None
    user_id = stored.user_id or item.user_id
    if not user_id:
        log.warning(
            "google credential update skipped: credential %s has no user_id, "
            "its tokens cannot be encrypted",
            stored.id,
        )
    return user_id or None


def credential_filter_for_user(email, user_id) -> dict:
    """Mongo filter of :meth:`OauthCredentialRepository.delete_oauth_credential_for_user`."""
    legacy = {"email": email, "user_id": {"$in": [None, ""]}}
    if not user_id:
        return legacy
    return {"$or": [{"user_id": user_id}, legacy]}


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

    @write_op(replay=True)
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
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            return await oauth_credential_document.save()
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    @write_op(replay=True)
    async def update(
        self, email: str, item: Oauth2CredentialDocument
    ) -> Oauth2CredentialDocument:
        """
        Update an OAuth2 credential document.

        The stored credential with the given email is updated, its tokens
        encrypted with the user's key. Nothing is written when there is no
        stored credential or no user id to derive the key from
        (see :func:`update_key`); the caller then gets ``item`` back as given.

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
            user_id = update_key(document, item)
            if not user_id:
                return WriteResult(item, [])  # nothing written
            credentials = item.credentials
            item.id = document.id
            item.user_id = user_id
            item.credentials = OauthCredentialRepository.encrypt_token(
                user_id=user_id, token=json.dumps(dict(item.credentials))
            )
            await item.save()
            # what was stored (encrypted) is not what the caller gets (decrypted)
            stored = item.model_copy(deep=True)
            item.credentials = credentials
            return WriteResult(item, [stored])

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

    async def list_all(self) -> list[Oauth2CredentialDocument]:
        """Every credential, as stored (encrypted) — for housekeeping."""
        return await Oauth2CredentialDocument.find().to_list()

    @write_op
    async def save(
        self, document: Oauth2CredentialDocument
    ) -> Oauth2CredentialDocument:
        return await document.save()

    @write_op
    async def delete_oauth_credential_for_user(self, email: EmailStr, user_id: str):
        """The account's credentials: by its user id, and by email only the
        legacy rows that have no user id. Another account whose email equals
        this one (in any case) keeps its credential."""
        return await Oauth2CredentialDocument.find(
            credential_filter_for_user(email, user_id)
        ).delete()
