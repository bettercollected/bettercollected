from datetime import datetime
from typing import List

from auth.app.models.credential import CredentialDocument
from common.models.user import UserInfo


# TODO : Refactor this
class CredentialRepository:

    @staticmethod
    async def get_credential(email: str, provider: str):
        return await CredentialDocument.find_one({"email": email, "provider": provider})

    # Get all credentials associated with email
    @staticmethod
    async def get_all_credentials(email: str) -> List[CredentialDocument]:
        return await CredentialDocument.find_many({"email": email}).to_list()

    @staticmethod
    async def save_credentials(user_info: UserInfo):
        credential = await CredentialRepository.get_credential(email=user_info.email, provider=user_info.provider)
        if not credential:
            credential = CredentialDocument()
            credential.created_at = datetime.utcnow()
            credential.email = user_info.email
            credential.provider = user_info.provider
        credential.access_token = user_info.access_token
        credential.refresh_token = user_info.refresh_token
        credential.access_token_expires = user_info.expires_in
        credential.updated_at = datetime.utcnow()
        await credential.save()

    @staticmethod
    async def revoke_credentials(email: str, provider: str):
        exists = await CredentialRepository.get_credential(email=email, provider=provider)
        if exists:
            return await exists.delete()
        return None
