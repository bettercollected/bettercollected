import datetime as dt
from typing import Any, Dict, List

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from pymongo import ASCENDING, IndexModel

from backend.app.handlers.database import entity


@entity
class UserAIPreferenceMemoryDocument(MongoDocument):
    """The AI's memory of how ONE creator likes forms, in ONE workspace
    (plan §2.4) — a living document the user owns.

    One fact per entry ("prefers pages under 5 questions", "titles in
    sentence case"), extracted from AI sessions or added by hand, each with a
    timestamp and source. Injected at the LOWEST precedence: the user's
    request and the org profile always override. Deliberately not embeddings —
    the user can read, edit and delete every line.
    """

    workspace_id: PydanticObjectId
    user_id: str
    # [{"id": str, "text": str, "at": iso8601, "source": "extracted"|"manual"}]
    entries: List[Dict[str, Any]] = []

    class Settings:
        name = "ai_preference_memories"
        indexes = [
            IndexModel(
                [("workspace_id", ASCENDING), ("user_id", ASCENDING)],
                unique=True,
                name="workspace_user_unique",
            )
        ]
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
