import datetime as dt
import enum
from typing import Optional

from beanie import PydanticObjectId
from pymongo import IndexModel
from pymongo.errors import OperationFailure

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


DELETION_REQUEST_INDEX = "uq_deletion_requests_form_response_provider_workspace"
# The unique (form_id, response_id, provider) key from before requests were
# per workspace, under Mongo's default name. Beanie never drops an index, so a
# database from before still holds it: drop_legacy_deletion_request_index.
LEGACY_DELETION_REQUEST_INDEX = "form_id_1_response_id_1_provider_1"


async def drop_legacy_deletion_request_index(collection) -> bool:
    """Drop the superseded per-response unique index from the
    ``responses_deletion_requests`` collection if it is still there (it would
    refuse a workspace's request while another workspace has one for its copy
    of the same response). Idempotent; True when it dropped it."""
    if LEGACY_DELETION_REQUEST_INDEX not in await collection.index_information():
        return False
    try:
        await collection.drop_index(LEGACY_DELETION_REQUEST_INDEX)
    except OperationFailure as error:
        if error.code != 27:  # IndexNotFound: another process dropped it meanwhile
            raise
    return True


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
        # One request per response, provider and workspace (as Postgres, app
        # revision 0020): each workspace holding a copy of a provider response
        # files its own. A missing or null workspace_id (a request stored
        # before #768) indexes as null, so two of those for the same response
        # still collide, as NULLS NOT DISTINCT does in Postgres.
        indexes = [
            IndexModel(
                [
                    ("form_id", 1),
                    ("response_id", 1),
                    ("provider", 1),
                    ("workspace_id", 1),
                ],
                unique=True,
                name=DELETION_REQUEST_INDEX,
            )
        ]
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
