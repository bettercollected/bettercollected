import datetime as dt
from typing import Optional

from common.records import Record


class UserFeedbackDocument(Record):
    reason_for_deletion: str
    feedback: Optional[str] = None

    class Settings:
        name = "user_feedback"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
