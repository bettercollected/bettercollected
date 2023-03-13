from datetime import datetime
from typing import List

from typeform.app.schemas.credential import CredentialDocument
from common.models.user import UserInfo, Token


# TODO : Refactor this
class CredentialRepository:
    @staticmethod
    async def get_credential(email: str):
        return await CredentialDocument.find_one({"email": email})

    # Get all credentials associated with email
    @staticmethod
    async def get_all_credentials(email: str) -> List[CredentialDocument]:
        return await CredentialDocument.find_many({"email": email}).to_list()

    @staticmethod
    async def save_credentials(user_info: UserInfo, token: Token):
        credential = await CredentialRepository.get_credential(email=user_info.email)
        if not credential:
            credential = CredentialDocument(email=user_info.email)
            credential.created_at = datetime.utcnow()
        credential.access_token = token.access_token
        credential.refresh_token = token.refresh_token
        credential.access_token_expires = token.expires_in
        credential.updated_at = datetime.utcnow()
        await credential.save()

    @staticmethod
    async def revoke_credentials(email: str):
        exists = await CredentialRepository.get_credential(email=email)
        if exists:
            return await exists.delete()
        return None
