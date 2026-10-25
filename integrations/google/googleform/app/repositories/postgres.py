"""Postgres twin of the google integration's credential repository."""

import json
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from pydantic.networks import EmailStr
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.db import PostgresRepositoryBase, WriteResult
from common.enums.form_provider import FormProvider
from common.clock import utcnow
from googleform.app.repositories.oauth_credential import (
    OauthCredentialRepository,
    update_key,
)
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.db.models import OAuthCredentialRow


def _database_error():
    return HTTPException(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=MESSAGE_DATABASE_EXCEPTION
    )


class PostgresOauthCredentialRepository(PostgresRepositoryBase):
    row = OAuthCredentialRow
    document = Oauth2CredentialDocument

    async def get(
        self,
        email: str,
        provider: FormProvider = FormProvider.GOOGLE,
        user_id: str = None,
    ) -> Oauth2CredentialDocument | None:
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
        try:
            provider = item.provider or FormProvider.GOOGLE
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
            await self.save_document(item)
            stored = item.model_copy(deep=True)
            item.credentials = credentials
            return WriteResult(item, [stored])
        except SQLAlchemyError:
            raise _database_error()

    async def list_all(self) -> list[Oauth2CredentialDocument]:
        return await self.many()

    async def save(
        self, document: Oauth2CredentialDocument
    ) -> Oauth2CredentialDocument:
        return await self.save_document(document)

    async def delete_oauth_credential_for_user(self, email: EmailStr, user_id: str):
        return await self.delete_where(
            or_(
                OAuthCredentialRow.email == email, OAuthCredentialRow.user_id == user_id
            )
        )
