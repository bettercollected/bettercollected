import datetime as dt
from typing import Optional

from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity


@entity
class UserFeedbackDocument(MongoDocument):
    reason_for_deletion: str
    feedback: Optional[str]

    class Settings:
        name = "user_feedback"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
