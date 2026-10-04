import datetime as dt
import enum
from typing import Optional

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from pydantic import field_validator
from pymongo import IndexModel


class DomainStatus(str, enum.Enum):
    PENDING = "pending"  # claimed, never checked
    VERIFIED = "verified"
    FAILED = "failed"  # not verified, the last check failed


class WorkspaceDomainDocument(MongoDocument):
    """An email domain a workspace claims, proven by a DNS TXT record.

    ``verified_domain`` equals ``domain`` while the claim is verified and is
    unset otherwise; it is unique in both stores, so a domain is verified by
    at most one workspace and the first verification wins. Pending claims of
    the same domain by other workspaces can never verify while it is held.
    """

    workspace_id: PydanticObjectId
    domain: str  # canonical ASCII (punycode), lower case
    verification_token: str
    method: str = "dns_txt"
    status: DomainStatus = DomainStatus.PENDING
    verified_domain: Optional[str] = None
    created_by: str
    verified_at: Optional[dt.datetime] = None
    verified_by: Optional[str] = None
    last_checked_at: Optional[dt.datetime] = None
    # code of the last check's failure (dns_txt module constants), None on success
    last_check_error: Optional[str] = None
    # failed checks in a row; on a verified domain only those that found the
    # record missing or wrong count, not resolver timeouts or errors
    failed_checks: int = 0
    # set once a verified domain failed LOSS_AFTER_FAILED_CHECKS re-checks in a
    # row; it stays verified (no automatic transfer), a passing check clears it
    verification_lost_at: Optional[dt.datetime] = None

    @field_validator("verified_at", "last_checked_at", "verification_lost_at")
    @classmethod
    def _utc(cls, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
        # Mongo hands datetimes back without a zone; they are UTC
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "workspace_domains"
        indexes = [
            IndexModel([("workspace_id", 1), ("domain", 1)], unique=True),
            IndexModel([("domain", 1)]),
            IndexModel(
                [("verified_domain", 1)],
                unique=True,
                partialFilterExpression={"verified_domain": {"$type": "string"}},
            ),
            IndexModel([("status", 1), ("last_checked_at", 1)]),
        ]
