import datetime as dt
import enum
from typing import Optional

from pymongo import IndexModel

from common.configs.mongo_document import MongoDocument
from common.models.standard_form import StandardFormResponse


class FormResponseDocument(MongoDocument, StandardFormResponse):
    class Settings:
        name = "form_responses"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class DeletionRequestStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"


class FormResponseDeletionRequest(MongoDocument):
    form_id: str
    response_id: str
    provider: str
    status: DeletionRequestStatus = DeletionRequestStatus.PENDING
    deleted_at: Optional[str]
    created_at: Optional[str] = dt.datetime.utcnow()

    class Settings:
        name = "responses_deletion_requests"
        indexes = [
            IndexModel(
                [("form_id", 1), ("response_id", 1), ("provider", 1)], unique=True
            )
        ]
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
