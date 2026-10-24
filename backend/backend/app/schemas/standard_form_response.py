import datetime as dt
import enum
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field
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
    # closed by staff without deleting, for one of DeclineReason
    DECLINED = "declined"


class DeclineReason(str, enum.Enum):
    """Why staff declined a deletion request (GDPR Art. 17(3), Art. 12(6)).
    A fixed list on purpose: no free text, so no personal data."""

    LEGAL_OBLIGATION = "legal_obligation"
    LEGAL_CLAIMS = "legal_claims"
    PUBLIC_INTEREST = "public_interest"
    IDENTITY_NOT_VERIFIED = "identity_not_verified"
    OTHER = "other"


DELETION_REQUEST_INDEX = "uq_deletion_requests_form_response_provider_workspace"
# One request per response, provider and workspace (as Postgres, app revision
# 0020): each workspace holding a copy of a provider response files its own. A
# missing or null workspace_id (a request stored before #768) indexes as null,
# so two of those for the same response still collide, as NULLS NOT DISTINCT
# does in Postgres. Built at startup after Beanie (handlers/database.py).
DELETION_REQUEST_INDEX_MODEL = IndexModel(
    [("form_id", 1), ("response_id", 1), ("provider", 1), ("workspace_id", 1)],
    unique=True,
    name=DELETION_REQUEST_INDEX,
)
# The unique (form_id, response_id, provider) key from before requests were
# per workspace, under Mongo's default name (Beanie built it from the
# document's settings, and never drops an index): dropped at startup by
# drop_legacy_deletion_request_index.
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


class DeletionRequestClosure(BaseModel):
    """One close of a deletion request (ids only)."""

    status: str
    # "staff" (closed by hand) or "import" (the source no longer has it)
    source: str
    at: str  # ISO 8601, UTC
    by: Optional[str] = None  # the staff user id
    reason: Optional[str] = None  # DeclineReason value, declines only


def _iso(at: dt.datetime) -> str:
    return at.astimezone(dt.timezone.utc).isoformat() if at.tzinfo else at.isoformat()


def staff_closure(status, by: str, at: dt.datetime, reason=None) -> DeletionRequestClosure:
    return DeletionRequestClosure(
        status=getattr(status, "value", status),
        source="staff",
        at=_iso(at),
        by=by,
        reason=getattr(reason, "value", reason),
    )


def import_closure(at: dt.datetime) -> DeletionRequestClosure:
    return DeletionRequestClosure(
        status=DeletionRequestStatus.SUCCESS.value, source="import", at=_iso(at)
    )


DELETION_REQUEST_INDEX = "uq_deletion_requests_form_response_provider_workspace"
# One request per response, provider and workspace (as Postgres, app revision
# 0020): each workspace holding a copy of a provider response files its own. A
# missing or null workspace_id (a request stored before #768) indexes as null,
# so two of those for the same response still collide, as NULLS NOT DISTINCT
# does in Postgres. Built at startup after Beanie (handlers/database.py).
DELETION_REQUEST_INDEX_MODEL = IndexModel(
    [("form_id", 1), ("response_id", 1), ("provider", 1), ("workspace_id", 1)],
    unique=True,
    name=DELETION_REQUEST_INDEX,
)
# The unique (form_id, response_id, provider) key from before requests were
# per workspace, under Mongo's default name (Beanie built it from the
# document's settings, and never drops an index): dropped at startup by
# drop_legacy_deletion_request_index.
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
    # Who closed the request by hand and when (the staff path, which needs no
    # provider): the audit record of the decision. None when it was closed by
    # deleting the response or by an import that no longer has it.
    closed_by: Optional[str] = None
    closed_at: Optional[dt.datetime] = None
    decline_reason: Optional[DeclineReason] = None
    # Every close, oldest first (append only): a staff decision, or an import
    # that no longer has the response. A later close never overwrites an
    # earlier one (a declined request whose response then leaves the source
    # keeps its decline here and gets a second entry).
    closures: List[DeletionRequestClosure] = Field(default_factory=list)

    class Settings:
        # No indexes here: DELETION_REQUEST_INDEX_MODEL is built (and the
        # legacy index dropped) after Beanie, by handlers/database.py, so
        # neither can stop the service from starting.
        name = "responses_deletion_requests"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
