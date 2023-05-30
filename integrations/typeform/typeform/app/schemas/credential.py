from typing import Optional

from beanie import Indexed, PydanticObjectId

from common.schemas.base_schema import BaseDocument
from typeform.app.services.database_service import entity


@entity
class CredentialDocument(BaseDocument):
    user_id: Optional[PydanticObjectId]
    email: Indexed(str, unique=True)
    access_token: Optional[str] | bytes
    refresh_token: Optional[str] | bytes
    access_token_expires: Optional[int]
    refresh_token_expires: Optional[int]
