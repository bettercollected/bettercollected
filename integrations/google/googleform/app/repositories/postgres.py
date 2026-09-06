"""Postgres twins of the google integration's repositories."""

import json
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Any, List

from fastapi import HTTPException
from pydantic.networks import EmailStr
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.db import PostgresRepositoryBase, WriteResult
from common.enums.form_provider import FormProvider
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.google_form import GoogleFormDocument
from googleform.app.schemas.google_form_response import GoogleFormResponseDocument
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.db.models import (
    GoogleFormResponseRow,
    GoogleFormRow,
    OAuthCredentialRow,
)


def _provider(provider) -> str:
    """Mongo stores the enum's value; ``str(FormProvider.GOOGLE)`` is not it."""
    return provider.value if isinstance(provider, Enum) else str(provider)


def _database_error():
    return HTTPException(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=MESSAGE_DATABASE_EXCEPTION
    )


class PostgresFormRepository(PostgresRepositoryBase):
    row = GoogleFormRow
    document = GoogleFormDocument

    async def list(self) -> List[GoogleFormDocument]:
        try:
            return await self.many(GoogleFormRow.provider == FormProvider.GOOGLE.value)
        except SQLAlchemyError:
            raise _database_error()

    async def get(
        self, form_id: str, provider: FormProvider | str
    ) -> GoogleFormDocument | None:
        try:
            return await self.one(
                GoogleFormRow.google_form_id == form_id,
                GoogleFormRow.provider == _provider(provider),
            )
        except SQLAlchemyError:
            raise _database_error()

    async def add(self, item: GoogleFormDocument) -> GoogleFormDocument:
        return item  # the Mongo implementation is a no-op too

    async def update(
        self, form_id: str, item: GoogleFormDocument
    ) -> GoogleFormDocument:
        try:
            provider = item.provider if item.provider else FormProvider.GOOGLE
            document = await self.get(form_id, provider)
            if document:
                item.id = document.id
            item.provider = provider
            return await self.upsert(item)
        except SQLAlchemyError:
            raise _database_error()

    async def delete(self, form_id: str, provider: FormProvider):
        return HTTPStatus.NO_CONTENT  # as the original


class PostgresFormResponseRepository(PostgresRepositoryBase):
    row = GoogleFormResponseRow
    document = GoogleFormResponseDocument

    async def list(self) -> List[GoogleFormResponseDocument]:
        try:
            return await self.many(
                GoogleFormResponseRow.provider == FormProvider.GOOGLE.value
            )
        except SQLAlchemyError:
            raise _database_error()

    async def list_form_responses(
        self, form_id: str
    ) -> List[GoogleFormResponseDocument]:
        try:
            return await self.many(
                GoogleFormResponseRow.google_form_id == form_id,
                GoogleFormResponseRow.provider == FormProvider.GOOGLE.value,
            )
        except SQLAlchemyError:
            raise _database_error()

    async def get(
        self, response_id: str, provider: FormProvider | str
    ) -> GoogleFormResponseDocument | None:
        try:
            return await self.one(
                GoogleFormResponseRow.google_response_id == response_id,
                GoogleFormResponseRow.provider == _provider(provider),
            )
        except SQLAlchemyError:
            raise _database_error()

    async def add(self, item: GoogleFormResponseDocument) -> GoogleFormResponseDocument:
        try:
            return await self.upsert(GoogleFormResponseDocument(**item.dict()))
        except SQLAlchemyError:
            raise _database_error()

    async def update(
        self, response_id: str, item: GoogleFormResponseDocument
    ) -> GoogleFormResponseDocument:
        try:
            provider = item.provider if item.provider else FormProvider.GOOGLE
            document = await self.get(response_id, provider)
            if document:
                item.id = document.id
            return await self.upsert(item)
        except SQLAlchemyError:
            raise _database_error()

    async def delete(
        self, response_id: str, provider: FormProvider = FormProvider.GOOGLE
    ):
        try:
            document = await self.get(response_id, provider)
            if document:
                await self.delete_by_id(document.id)
                return HTTPStatus.NO_CONTENT
            return HTTPStatus.NOT_FOUND
        except SQLAlchemyError:
            raise _database_error()


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
            return await self.upsert(
                Oauth2CredentialDocument(
                    user_id=user_id,
                    email=email,
                    provider=provider,
                    credentials=credentials,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
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
            credentials = item.credentials
            if document:
                item.id = document.id
            if document.user_id:
                item.credentials = OauthCredentialRepository.encrypt_token(
                    user_id=document.user_id, token=json.dumps(dict(item.credentials))
                )
            await self.upsert(item)
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
        return await self.upsert(document)

    async def delete_oauth_credential_for_user(self, email: EmailStr, user_id: str):
        return await self.delete_where(
            or_(
                OAuthCredentialRow.email == email, OAuthCredentialRow.user_id == user_id
            )
        )
