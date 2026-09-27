import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId

from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from common.db.routing import write_op


class FormImportRepository:
    @write_op
    async def save(self, document: FormImportDocument) -> FormImportDocument:
        return await document.save()

    async def get(self, import_id: PydanticObjectId) -> Optional[FormImportDocument]:
        try:
            import_id = PydanticObjectId(import_id)
        except Exception:  # noqa: BLE001 — not an ObjectId: no such import
            return None
        return await FormImportDocument.find_one({"_id": import_id})

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId, limit: int = 20
    ) -> List[FormImportDocument]:
        return (
            await FormImportDocument.find({"workspace_id": workspace_id})
            .sort([("created_at", -1), ("_id", -1)])
            .limit(limit)
            .to_list()
        )

    async def count_created_since(
        self, workspace_id: PydanticObjectId, since: dt.datetime
    ) -> int:
        return await FormImportDocument.find(
            {"workspace_id": workspace_id, "created_at": {"$gte": since}}
        ).count()

    async def count_active(self, workspace_id: PydanticObjectId) -> int:
        return await FormImportDocument.find(
            {"workspace_id": workspace_id, "status": {"$in": list(ImportStatus.ACTIVE)}}
        ).count()

    @write_op
    async def delete_by_form_ids(self, form_ids: List[str]) -> int:
        result = await FormImportDocument.find({"form_id": {"$in": form_ids}}).delete()
        return result.deleted_count if result else 0
