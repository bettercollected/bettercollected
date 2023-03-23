from typing import Optional

from beanie import Indexed

from common.schemas.base_schema import BaseDocument

from typeform.app.services.database_service import entity


@entity
class CredentialDocument(BaseDocument):
    email: Indexed(str, unique=True)
    access_token: Optional[str]
    refresh_token: Optional[str]
    access_token_expires: Optional[int]
    refresh_token_expires: Optional[int]
