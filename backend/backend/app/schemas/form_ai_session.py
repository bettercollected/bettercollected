import datetime as dt
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity


@entity
class FormAISessionDocument(MongoDocument):
    """One AI form-editing conversation (plan §2.2).

    Powers chat history for context, per-workspace usage accounting, and the
    preference-memory extraction later (P1.7). Messages hold role/content plus
    the ops the assistant applied and their results — the auditable record of
    what the AI actually changed.
    """

    workspace_id: PydanticObjectId
    form_id: str
    user_id: str
    provider: Optional[str] = None
    messages: List[Dict[str, Any]] = []

    class Settings:
        name = "form_ai_sessions"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
