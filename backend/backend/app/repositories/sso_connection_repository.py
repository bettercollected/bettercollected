import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
)
from common.db.routing import write_op


class SsoConnectionExists(Exception):
    """A connection with this Polis clientID is already recorded."""


def _object_id(value) -> Optional[PydanticObjectId]:
    try:
        return PydanticObjectId(value)
    except Exception:  # noqa: BLE001 — not an ObjectId: matches nothing
        return None


class SsoConnectionRepository:
    @write_op
    async def create(self, document: SsoConnectionDocument) -> SsoConnectionDocument:
        try:
            return await document.insert()
        except DuplicateKeyError:
            raise SsoConnectionExists(document.polis_client_id)

    @write_op
    async def save(self, document: SsoConnectionDocument) -> SsoConnectionDocument:
        return await document.save()

    async def get(self, connection_id) -> Optional[SsoConnectionDocument]:
        object_id = _object_id(connection_id)
        if object_id is None:
            return None
        return await SsoConnectionDocument.find_one({"_id": object_id})

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[SsoConnectionDocument]:
        return (
            await SsoConnectionDocument.find(
                {"workspace_id": PydanticObjectId(workspace_id)}
            )
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    async def count_by_workspace(self, workspace_id: PydanticObjectId) -> int:
        return await SsoConnectionDocument.find(
            {"workspace_id": PydanticObjectId(workspace_id)}
        ).count()

    async def find_enabled(
        self, workspace_id: PydanticObjectId
    ) -> Optional[SsoConnectionDocument]:
        """The workspace's enabled connection (the latest enabled, should a
        race have left two)."""
        found = (
            await SsoConnectionDocument.find(
                {
                    "workspace_id": PydanticObjectId(workspace_id),
                    "status": SsoConnectionStatus.ENABLED.value,
                }
            )
            .sort([("enabled_at", -1), ("_id", -1)])
            .limit(1)
            .to_list()
        )
        return found[0] if found else None

    @write_op
    async def disable_others(
        self,
        workspace_id: PydanticObjectId,
        keep_id: PydanticObjectId,
        disabled_by: str,
        now: dt.datetime,
    ) -> int:
        """Disable every enabled connection of the workspace but ``keep_id``."""
        result = await SsoConnectionDocument.find(
            {
                "workspace_id": PydanticObjectId(workspace_id),
                "status": SsoConnectionStatus.ENABLED.value,
                "_id": {"$ne": PydanticObjectId(keep_id)},
            }
        ).update(
            {
                "$set": {
                    "status": SsoConnectionStatus.DISABLED.value,
                    "disabled_at": now,
                    "disabled_by": disabled_by,
                    "updated_at": now,
                }
            }
        )
        return result.modified_count if result else 0

    @write_op
    async def delete(self, connection_id: PydanticObjectId) -> int:
        result = await SsoConnectionDocument.find(
            {"_id": PydanticObjectId(connection_id)}
        ).delete()
        return result.deleted_count if result else 0

    @write_op
    async def delete_by_workspace_ids(
        self, workspace_ids: List[PydanticObjectId]
    ) -> int:
        result = await SsoConnectionDocument.find(
            {"workspace_id": {"$in": [PydanticObjectId(w) for w in workspace_ids]}}
        ).delete()
        return result.deleted_count if result else 0
