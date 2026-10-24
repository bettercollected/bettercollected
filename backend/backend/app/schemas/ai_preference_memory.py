import datetime as dt
from typing import Any, Dict, List, Optional

from common.records import Record, RecordId


class UserAIPreferenceMemoryDocument(Record):
    """The AI's memory of how ONE creator likes forms, in ONE workspace
    (plan §2.4) — a living document the user owns.

    One fact per entry ("prefers pages under 5 questions", "titles in
    sentence case"), extracted from AI sessions or added by hand, each with a
    timestamp and source. Injected at the LOWEST precedence: the user's
    request and the org profile always override. Deliberately not embeddings —
    the user can read, edit and delete every line.
    """

    # unique with user_id in Postgres (app migration 0018)
    workspace_id: RecordId
    user_id: str
    # [{"id": str, "text": str, "at": iso8601, "source": "extracted"|"manual"}]
    entries: List[Dict[str, Any]] = []
    # "Learn my preferences" (#715): extraction after chat turns runs only
    # when the user turned this on (default off); manual entries don't need it.
    learn_preferences: bool = False
    learn_preferences_at: Optional[dt.datetime] = None

    class Settings:
        name = "ai_preference_memories"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
