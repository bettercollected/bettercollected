import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from backend.app.schemas.workspace_domain import DomainStatus, WorkspaceDomainDocument
from common.db.routing import write_op


class DomainAlreadyClaimed(Exception):
    """The workspace already has a claim for this domain."""


class DomainVerifiedElsewhere(Exception):
    """Another workspace holds this domain verified."""


def _object_id(value) -> Optional[PydanticObjectId]:
    try:
        return PydanticObjectId(value)
    except Exception:  # noqa: BLE001 — not an ObjectId: matches nothing
        return None


class WorkspaceDomainRepository:
    @write_op
    async def create(
        self, document: WorkspaceDomainDocument
    ) -> WorkspaceDomainDocument:
        """Insert a new claim; DomainAlreadyClaimed when the workspace has one
        for the domain (unique workspace + domain)."""
        try:
            return await document.insert()
        except DuplicateKeyError:
            raise DomainAlreadyClaimed(document.domain)

    @write_op
    async def save(self, document: WorkspaceDomainDocument) -> WorkspaceDomainDocument:
        """Store a check's outcome. A document carrying ``verified_domain``
        raises DomainVerifiedElsewhere when another workspace holds it, which
        is what makes the first verification win."""
        try:
            return await document.save()
        except DuplicateKeyError:
            raise DomainVerifiedElsewhere(document.domain)

    async def get(self, domain_id) -> Optional[WorkspaceDomainDocument]:
        object_id = _object_id(domain_id)
        if object_id is None:
            return None
        return await WorkspaceDomainDocument.find_one({"_id": object_id})

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceDomainDocument]:
        return (
            await WorkspaceDomainDocument.find(
                {"workspace_id": PydanticObjectId(workspace_id)}
            )
            .sort([("domain", 1)])
            .to_list()
        )

    async def count_by_workspace(self, workspace_id: PydanticObjectId) -> int:
        return await WorkspaceDomainDocument.find(
            {"workspace_id": PydanticObjectId(workspace_id)}
        ).count()

    async def find_verified(self, domain: str) -> Optional[WorkspaceDomainDocument]:
        return await WorkspaceDomainDocument.find_one({"verified_domain": domain})

    async def list_due_for_recheck(
        self, checked_before: dt.datetime, limit: int
    ) -> List[WorkspaceDomainDocument]:
        """Verified domains last checked before ``checked_before``, the
        longest unchecked first."""
        return (
            await WorkspaceDomainDocument.find(
                {
                    "status": DomainStatus.VERIFIED.value,
                    "last_checked_at": {"$lt": checked_before},
                }
            )
            .sort([("last_checked_at", 1), ("_id", 1)])
            .limit(limit)
            .to_list()
        )

    @write_op
    async def delete(self, domain_id: PydanticObjectId) -> int:
        result = await WorkspaceDomainDocument.find(
            {"_id": PydanticObjectId(domain_id)}
        ).delete()
        return result.deleted_count if result else 0

    @write_op
    async def delete_by_workspace_ids(
        self, workspace_ids: List[PydanticObjectId]
    ) -> int:
        result = await WorkspaceDomainDocument.find(
            {"workspace_id": {"$in": [PydanticObjectId(w) for w in workspace_ids]}}
        ).delete()
        return result.deleted_count if result else 0
