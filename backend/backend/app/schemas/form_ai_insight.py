import datetime as dt
from typing import Any, Dict, Optional

from common.records import Record, RecordId


class FormAIInsightDocument(Record):
    """Cached AI summary of a form's responses (plan §2 'response summaries',
    phase P3). One document per form, replaced on each regeneration.

    Exists so viewing insights is free after the one explicit, creator-
    triggered generation — the AI reads respondent data ONLY at that moment,
    never in the background.
    """

    workspace_id: RecordId
    form_id: str
    payload: Dict[str, Any]
    # How much of the data the summary actually saw — shown to the creator.
    response_count: int
    total_responses: int
    generated_by: Optional[str] = None
    generated_at: dt.datetime

    class Settings:
        name = "form_ai_insights"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
