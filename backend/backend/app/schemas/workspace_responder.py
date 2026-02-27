from typing import Optional, List, Dict

from beanie import PydanticObjectId

from backend.app.handlers.database import entity
from common.configs.mongo_document import MongoDocument


@entity
class WorkspaceTags(MongoDocument):
    workspace_id: PydanticObjectId
    title: str

    class Settings:
        name = "workspace_tags"


@entity
class WorkspaceResponderDocument(MongoDocument):
    workspace_id: PydanticObjectId
    user_id: Optional[str] = None
    email: str
    tags: Optional[List[PydanticObjectId]] = None
    metadata: Optional[Dict[str, str]] = None

    class Settings:
        name = "workspace_responder"
