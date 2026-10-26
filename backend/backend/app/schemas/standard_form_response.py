import datetime as dt
import enum
from typing import List, Optional

from pydantic import BaseModel, Field

from common.models.standard_form import StandardFormResponse
from common.records import Record, RecordId


class FormResponseDocument(Record, StandardFormResponse):
    # The workspace the response was collected in or imported into (#768): a
    # provider form linked to several workspaces has one form_id in all of
    # them. None only on responses stored before it existed (see
    # repositories/response_scope.py).
    workspace_id: Optional[RecordId] = None

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


# One request per response, provider and workspace (app revision 0020): each
# workspace holding a copy of a provider response files its own; a missing
# workspace_id (a request stored before #768) counts as one more workspace.


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


class FormResponseDeletionRequest(Record):
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
    workspace_id: Optional[RecordId] = None
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
        name = "responses_deletion_requests"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
