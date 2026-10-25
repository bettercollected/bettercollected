import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId

from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from common.db.routing import write_op


class WorkspaceAPIKeyRepository:
    @write_op
    async def save(self, document: WorkspaceAPIKeyDocument) -> WorkspaceAPIKeyDocument:
        return await document.save()

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceAPIKeyDocument]:
        return await WorkspaceAPIKeyDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    async def get_or_404(self, key_id: PydanticObjectId) -> WorkspaceAPIKeyDocument:
        """Raises the document layer's NotFoundError when missing, like Document.get."""
        return await WorkspaceAPIKeyDocument.get(key_id)

    async def find_by_key_hash(
        self, key_hash: str
    ) -> Optional[WorkspaceAPIKeyDocument]:
        return await WorkspaceAPIKeyDocument.find_one({"key_hash": key_hash})

    @write_op
    async def touch_last_used(self, key_id: PydanticObjectId, now: dt.datetime) -> bool:
        """Record that the key was used at ``now``: a conditional ``$set`` of
        ``last_used_at`` alone, only while the key is not revoked, so a
        revocation (or any other change) made since the caller read the key
        is never written back. Whether the key was live and touched. The
        value is stored as ``save()`` stores it (the document's ISO-string
        encoder)."""
        encode = WorkspaceAPIKeyDocument.get_settings().bson_encoders[dt.datetime]
        result = await WorkspaceAPIKeyDocument.get_pymongo_collection().update_one(
            {"_id": PydanticObjectId(key_id), "revoked": {"$ne": True}},
            {"$set": {"last_used_at": encode(now)}},
        )
        return result.matched_count == 1
