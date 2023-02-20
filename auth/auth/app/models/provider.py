from typing import Optional

from auth.app.services.database_service import entity
from common.configs.mongo_document import MongoDocument


@entity
class Provider(MongoDocument):
    provider_name: str
    basic_auth_url: Optional[str]
    oauth_url: Optional[str]
