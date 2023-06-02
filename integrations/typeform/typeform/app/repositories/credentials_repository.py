from datetime import datetime
from http import HTTPStatus
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import HTTPException
from pymongo.errors import (
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
    InvalidOperation,
)

from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_NOT_FOUND
from common.models.user import Token, UserInfo
from common.services.crypto_service import crypto_service
from typeform.app.schemas.credential import CredentialDocument


# TODO : Refactor this
class CredentialRepository:
    @staticmethod
    async def get_credential(email: str, user_id: Optional[str] = None):
        credential = await CredentialDocument.find_one(
            {"$or": [{"email": email}, {"user_id": PydanticObjectId(user_id)}]}
        )
        if credential:
            credential.access_token = CredentialRepository.decrypt_token(
                str(credential.user_id), token=credential.access_token
            )
            credential.refresh_token = CredentialRepository.decrypt_token(
                str(credential.user_id), token=credential.refresh_token
            )
        return credential

    @staticmethod
    async def get_all_credentials(email: str) -> List[CredentialDocument]:
        return await CredentialDocument.find_many({"email": email}).to_list()

    @staticmethod
    async def save_credentials(user_info: UserInfo, token: Token):
        credential = await CredentialRepository.get_credential(email=user_info.email)
        if not credential:
            credential = CredentialDocument(email=user_info.email)
            credential.created_at = datetime.utcnow()
        credential.user_id = user_info.user_id
        credential.access_token = CredentialRepository.encrypt_token(
            user_id=user_info.user_id, token=token.access_token
        )
        credential.refresh_token = CredentialRepository.encrypt_token(
            user_id=user_info.user_id, token=token.refresh_token
        )
        credential.access_token_expires = token.expires_in
        credential.updated_at = datetime.utcnow()
        await credential.save()

    @staticmethod
    async def update_credentials(email: str, token: Token):
        try:
            credentials_document = await CredentialRepository.get_credential(
                email=email
            )
            if not credentials_document:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, detail=MESSAGE_NOT_FOUND
                )
            if credentials_document.user_id:
                credentials_document.access_token = CredentialRepository.encrypt_token(
                    user_id=str(credentials_document.user_id), token=token.access_token
                )
                credentials_document.refresh_token = CredentialRepository.encrypt_token(
                    user_id=str(credentials_document.user_id), token=token.refresh_token
                )
            else:
                credentials_document.access_token = token.access_token
                credentials_document.refresh_token = token.refresh_token
            credentials_document.access_token_expires = token.expires_in
            credentials_document.updated_at = datetime.utcnow()
            await credentials_document.save()

        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_DATABASE_EXCEPTION,
            )

    @staticmethod
    def encrypt_token(user_id: str, token: str):
        return crypto_service.encrypt("personal", form_id=user_id, data=token)

    @staticmethod
    def decrypt_token(user_id: str, token: str):
        decrypted_token = crypto_service.decrypt(
            "personal", form_id=user_id, data=token
        )
        if isinstance(decrypted_token, bytes):
            decrypted_token = str(decrypted_token, "utf-8")
        return decrypted_token

    @staticmethod
    async def revoke_credentials(email: str):
        exists = await CredentialRepository.get_credential(email=email)
        if exists:
            return await exists.delete()
        return None
