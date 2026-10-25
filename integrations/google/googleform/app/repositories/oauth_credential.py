"""The google integration's credential repository: Postgres only.

The Mongo original and the routing between the two stores are gone since
4.1; Mongo is read only by the import from 4.0 (``python -m
googleform.migrate``).
"""

import json
import logging
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from pydantic.networks import EmailStr
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import SQLAlchemyError

from common.clock import utcnow
from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.db import PostgresRepositoryBase
from common.enums.form_provider import FormProvider
from common.services.crypto_service import crypto_service
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.db.models import OAuthCredentialRow

log = logging.getLogger(__name__)


def _database_error():
    return HTTPException(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=MESSAGE_DATABASE_EXCEPTION
    )


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


class OauthCredentialRepository(PostgresRepositoryBase):
    row = OAuthCredentialRow
    document = Oauth2CredentialDocument

    async def get(
        self,
        email: str,
        provider: FormProvider = FormProvider.GOOGLE,
        user_id: str = None,
    ) -> Oauth2CredentialDocument | None:
        """The credential stored for ``email``, decrypted, or None."""
        try:
            document = await self.one(OAuthCredentialRow.email == email)
            if document:
                document.credentials = OauthCredentialRepository.decrypt_token(
                    user_id=document.user_id, token=document.credentials
                )
                return document
            return None
        except SQLAlchemyError:
            raise _database_error()

    async def add(
        self,
        email: str,
        credentials: Any,
        user_id: str,
        provider: FormProvider = FormProvider.GOOGLE,
    ) -> Oauth2CredentialDocument:
        """Store a new credential (encrypted) and return what was stored."""
        try:
            credentials = OauthCredentialRepository.encrypt_token(
                user_id=user_id, token=json.dumps(dict(credentials))
            )
            return await self.save_document(
                Oauth2CredentialDocument(
                    user_id=user_id,
                    email=email,
                    provider=provider,
                    credentials=credentials,
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
        except SQLAlchemyError:
            raise _database_error()

    async def update(
        self, email: str, item: Oauth2CredentialDocument
    ) -> Oauth2CredentialDocument:
        """Store ``item`` over the credential of ``email`` (encrypted); the
        caller gets it back decrypted. Nothing is written when there is no
        stored credential or no user id to derive the key from
        (:func:`update_key`); the caller then gets ``item`` back as given."""
        try:
            provider = item.provider or FormProvider.GOOGLE
            document = await self.get(email, provider)
            user_id = update_key(document, item)
            if not user_id:
                return item  # nothing written
            credentials = item.credentials
            item.id = document.id
            item.user_id = user_id
            item.credentials = OauthCredentialRepository.encrypt_token(
                user_id=user_id, token=json.dumps(dict(item.credentials))
            )
            await self.save_document(item)
            item.credentials = credentials
            return item
        except SQLAlchemyError:
            raise _database_error()

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
        return await self.many()

    async def save(
        self, document: Oauth2CredentialDocument
    ) -> Oauth2CredentialDocument:
        return await self.save_document(document)

    async def delete_oauth_credential_for_user(self, email: EmailStr, user_id: str):
        """The account's credentials: by its user id, and by email only the
        legacy rows that have no user id. Another account whose email equals
        this one (in any case) keeps its credential."""
        legacy = and_(
            func.coalesce(OAuthCredentialRow.user_id, "") == "",
            OAuthCredentialRow.email == email,
        )
        if not user_id:
            return await self.delete_where(legacy)
        return await self.delete_where(or_(OAuthCredentialRow.user_id == user_id, legacy))
