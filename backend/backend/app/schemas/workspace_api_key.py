import datetime as dt
from typing import List, Optional

from beanie import Indexed, PydanticObjectId
from common.configs.mongo_document import MongoDocument
from typing_extensions import Annotated

from backend.app.handlers.database import entity


@entity
class WorkspaceAPIKeyDocument(MongoDocument):
    """A workspace-scoped API key (plan §2.5) — the credential MCP and the
    public API authenticate with.

    Only the SHA-256 of the token is stored; the full token is shown exactly
    once at creation. ``prefix`` (the first characters) is kept for display so
    a key can be recognized without being recoverable. Scopes gate what the
    key may do; ``created_by`` is the acting user for authorization checks.
    """

    workspace_id: PydanticObjectId
    name: str
    key_hash: Annotated[str, Indexed(unique=True)]
    prefix: str
    scopes: List[str] = []
    created_by: str
    revoked: bool = False
    last_used_at: Optional[dt.datetime] = None

    class Settings:
        name = "workspace_api_keys"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
