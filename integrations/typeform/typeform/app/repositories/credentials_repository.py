from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId

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
                credential.user_id, token=credential.access_token
            )
            credential.refresh_token = CredentialRepository.decrypt_token(
                credential.user_id, token=credential.refresh_token
            )
        return credential
        # Get all credentials associated with email

    @staticmethod
    async def get_all_credentials(email: str) -> List[CredentialDocument]:
        return await CredentialDocument.find_many({"email": email}).to_list()

    @staticmethod
    async def save_credentials(user_info: UserInfo, token: Token):
        credential = await CredentialRepository.get_credential(email=user_info.email)
        if not credential:
            credential = CredentialDocument(
                email=user_info.email, user_id=user_info.user_id
            )
            credential.created_at = datetime.utcnow()
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
    def encrypt_token(user_id: str, token: str):
        return crypto_service.encrypt("personal", form_id=user_id, data=token)

    @staticmethod
    def decrypt_token(user_id: str, token: str):
        decrypted_token = crypto_service.decrypt("personal", form_id=user_id, data=token)
        if isinstance(decrypted_token, bytes):
            decrypted_token = str(decrypted_token, "utf-8")
        return decrypted_token

    @staticmethod
    async def revoke_credentials(email: str):
        exists = await CredentialRepository.get_credential(email=email)
        if exists:
            return await exists.delete()
        return None
