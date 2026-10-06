import datetime as dt
import enum
from typing import Optional

from beanie import PydanticObjectId
from pymongo import IndexModel

from common.configs.mongo_document import MongoDocument
from common.models.standard_form import StandardFormResponse


class FormResponseDocument(MongoDocument, StandardFormResponse):
    # The workspace the response was collected in or imported into (#768): a
    # provider form linked to several workspaces has one form_id in all of
    # them. None only on responses stored before it existed (see
    # repositories/response_scope.py).
    workspace_id: Optional[PydanticObjectId] = None

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
    provider: Optional[str] = None
    dataOwnerIdentifier: Optional[str] = None
    # Anonymous responses are attributable only via this hash — without it a
    # request created for an anonymous response could never be listed back to
    # its owner.
    anonymous_identity: Optional[str] = None
    status: DeletionRequestStatus = DeletionRequestStatus.PENDING
    # the workspace of the response it covers (#768)
    workspace_id: Optional[PydanticObjectId] = None
    deleted_at: Optional[str] = None

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
