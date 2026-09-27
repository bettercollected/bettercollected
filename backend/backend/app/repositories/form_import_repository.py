import asyncio
import contextlib
import datetime as dt
import secrets
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from common.db.routing import write_op

# per-workspace start locks (Mongo only; the Postgres twin uses an advisory
# lock): one short-lived document per workspace, its _id the unique key
LOCKS = "form_import_locks"
# a start holds the lock for a count and an insert; a lease this long only
# matters if the process died holding it
LOCK_LEASE = dt.timedelta(seconds=30)
LOCK_WAIT_S = 10.0


class ImportLimitReached(Exception):
    """A workspace limit refused a new import (``code``: import_in_progress,
    daily_limit)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class FormImportRepository:
    @write_op
    async def save(self, document: FormImportDocument) -> FormImportDocument:
        return await document.save()

    @write_op(replay=True)
    async def create_within_limits(
        self,
        document: FormImportDocument,
        max_active: int,
        max_per_day: int,
        since: dt.datetime,
    ) -> FormImportDocument:
        """Insert ``document`` unless its workspace already has ``max_active``
        imports running or ``max_per_day`` created since ``since`` (raises
        ImportLimitReached). Starts in one workspace are serialised by a lock
        document, so two parallel uploads cannot both pass the counts."""
        workspace_id = document.workspace_id
        async with _workspace_lock(workspace_id):
            check_import_limits(
                await self.count_active(workspace_id),
                await self.count_created_since(workspace_id, since),
                max_active,
                max_per_day,
            )
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


def check_import_limits(
    active: int, today: int, max_active: int, max_per_day: int
) -> None:
    if active >= max_active:
        raise ImportLimitReached("import_in_progress")
    if today >= max_per_day:
        raise ImportLimitReached("daily_limit")


@contextlib.asynccontextmanager
async def _workspace_lock(workspace_id):
    """Hold the workspace's lock document. Taken by an upsert that only
    matches an expired lease: while another start holds it, the upsert tries
    to insert the same _id and fails with a duplicate key."""
    locks = FormImportDocument.get_pymongo_collection().database[LOCKS]
    key, token = str(workspace_id), secrets.token_hex(12)
    deadline = asyncio.get_running_loop().time() + LOCK_WAIT_S
    while True:
        now = dt.datetime.now(dt.timezone.utc)
        try:
            await locks.update_one(
                {"_id": key, "expires_at": {"$lt": now}},
                {"$set": {"token": token, "expires_at": now + LOCK_LEASE}},
                upsert=True,
            )
            break
        except DuplicateKeyError:
            if asyncio.get_running_loop().time() > deadline:
                # another start has held it for too long: report it as busy
                raise ImportLimitReached("import_in_progress")
            await asyncio.sleep(0.02)
    try:
        yield
    finally:
        await locks.delete_one({"_id": key, "token": token})
