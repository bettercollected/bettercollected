"""SCIM directory sync storage (docs/sso.md, "Directory sync"); the Postgres
twins are in ``postgres/identity.py``."""

import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimEventDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
)
from common.db.routing import write_op


class ScimDirectoryExists(Exception):
    """The workspace already has a directory (or the Polis id is taken)."""


class ScimEventSeen(Exception):
    """This event was accepted before (a retry or a replay)."""


def _object_id(value) -> Optional[PydanticObjectId]:
    try:
        return PydanticObjectId(value)
    except Exception:  # noqa: BLE001 — not an ObjectId: matches nothing
        return None


def _oids(values) -> List[PydanticObjectId]:
    return [PydanticObjectId(v) for v in values]


class ScimDirectoryRepository:
    @write_op
    async def create(self, document: ScimDirectoryDocument) -> ScimDirectoryDocument:
        try:
            return await document.insert()
        except DuplicateKeyError:
            raise ScimDirectoryExists(str(document.workspace_id))

    @write_op
    async def save(self, document: ScimDirectoryDocument) -> ScimDirectoryDocument:
        return await document.save()

    async def get(self, directory_id) -> Optional[ScimDirectoryDocument]:
        object_id = _object_id(directory_id)
        if object_id is None:
            return None
        return await ScimDirectoryDocument.find_one({"_id": object_id})

    async def find_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> Optional[ScimDirectoryDocument]:
        return await ScimDirectoryDocument.find_one(
            {"workspace_id": PydanticObjectId(workspace_id)}
        )

    async def list_all(self) -> List[ScimDirectoryDocument]:
        return await ScimDirectoryDocument.find({}).sort([("_id", 1)]).to_list()

    @write_op
    async def delete(self, directory_id: PydanticObjectId) -> int:
        result = await ScimDirectoryDocument.find(
            {"_id": PydanticObjectId(directory_id)}
        ).delete()
        return result.deleted_count if result else 0


class ScimUserRepository:
    @write_op
    async def save(self, document: ScimUserDocument) -> ScimUserDocument:
        return await document.save()

    async def get(self, scim_user_id) -> Optional[ScimUserDocument]:
        object_id = _object_id(scim_user_id)
        if object_id is None:
            return None
        return await ScimUserDocument.find_one({"_id": object_id})

    async def find(
        self, directory_id: PydanticObjectId, polis_user_id: str
    ) -> Optional[ScimUserDocument]:
        return await ScimUserDocument.find_one(
            {
                "directory_id": PydanticObjectId(directory_id),
                "polis_user_id": polis_user_id,
            }
        )

    async def find_by_email(
        self, workspace_id: PydanticObjectId, email: str
    ) -> List[ScimUserDocument]:
        """The workspace's directory users with this (lower-cased) email."""
        return (
            await ScimUserDocument.find(
                {"workspace_id": PydanticObjectId(workspace_id), "email": email}
            )
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    async def list_by_directory(
        self, directory_id: PydanticObjectId
    ) -> List[ScimUserDocument]:
        return (
            await ScimUserDocument.find({"directory_id": PydanticObjectId(directory_id)})
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    async def list_by_ids(self, ids: List[PydanticObjectId]) -> List[ScimUserDocument]:
        if not ids:
            return []
        return (
            await ScimUserDocument.find({"_id": {"$in": _oids(ids)}})
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    @write_op
    async def delete_by_directory(self, directory_id: PydanticObjectId) -> int:
        result = await ScimUserDocument.find(
            {"directory_id": PydanticObjectId(directory_id)}
        ).delete()
        return result.deleted_count if result else 0


class ScimGroupRepository:
    @write_op
    async def save(self, document: ScimGroupDocument) -> ScimGroupDocument:
        return await document.save()

    async def get(self, group_id) -> Optional[ScimGroupDocument]:
        object_id = _object_id(group_id)
        if object_id is None:
            return None
        return await ScimGroupDocument.find_one({"_id": object_id})

    async def find(
        self, directory_id: PydanticObjectId, polis_group_id: str
    ) -> Optional[ScimGroupDocument]:
        return await ScimGroupDocument.find_one(
            {
                "directory_id": PydanticObjectId(directory_id),
                "polis_group_id": polis_group_id,
            }
        )

    async def list_by_directory(
        self, directory_id: PydanticObjectId
    ) -> List[ScimGroupDocument]:
        return (
            await ScimGroupDocument.find(
                {"directory_id": PydanticObjectId(directory_id)}
            )
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    @write_op
    async def delete(self, group_id: PydanticObjectId) -> int:
        result = await ScimGroupDocument.find(
            {"_id": PydanticObjectId(group_id)}
        ).delete()
        return result.deleted_count if result else 0

    @write_op
    async def delete_by_directory(self, directory_id: PydanticObjectId) -> int:
        result = await ScimGroupDocument.find(
            {"directory_id": PydanticObjectId(directory_id)}
        ).delete()
        return result.deleted_count if result else 0


class ScimGroupMemberRepository:
    @write_op
    async def add(self, document: ScimGroupMemberDocument) -> ScimGroupMemberDocument:
        """``document.id`` is derived from the pair: adding twice is a no-op."""
        return await document.save()

    @write_op
    async def remove(
        self, group_id: PydanticObjectId, scim_user_id: PydanticObjectId
    ) -> int:
        result = await ScimGroupMemberDocument.find(
            {
                "group_id": PydanticObjectId(group_id),
                "scim_user_id": PydanticObjectId(scim_user_id),
            }
        ).delete()
        return result.deleted_count if result else 0

    async def list_by_user(
        self, scim_user_id: PydanticObjectId
    ) -> List[ScimGroupMemberDocument]:
        return (
            await ScimGroupMemberDocument.find(
                {"scim_user_id": PydanticObjectId(scim_user_id)}
            )
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    async def list_by_group(
        self, group_id: PydanticObjectId
    ) -> List[ScimGroupMemberDocument]:
        return (
            await ScimGroupMemberDocument.find({"group_id": PydanticObjectId(group_id)})
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    async def list_by_directory(
        self, directory_id: PydanticObjectId
    ) -> List[ScimGroupMemberDocument]:
        return (
            await ScimGroupMemberDocument.find(
                {"directory_id": PydanticObjectId(directory_id)}
            )
            .sort([("created_at", 1), ("_id", 1)])
            .to_list()
        )

    @write_op
    async def delete_by_group(self, group_id: PydanticObjectId) -> int:
        result = await ScimGroupMemberDocument.find(
            {"group_id": PydanticObjectId(group_id)}
        ).delete()
        return result.deleted_count if result else 0

    @write_op
    async def delete_by_user(self, scim_user_id: PydanticObjectId) -> int:
        result = await ScimGroupMemberDocument.find(
            {"scim_user_id": PydanticObjectId(scim_user_id)}
        ).delete()
        return result.deleted_count if result else 0

    @write_op
    async def delete_by_directory(self, directory_id: PydanticObjectId) -> int:
        result = await ScimGroupMemberDocument.find(
            {"directory_id": PydanticObjectId(directory_id)}
        ).delete()
        return result.deleted_count if result else 0


class ScimEventRepository:
    @write_op(replay=True)
    async def claim(
        self, document: ScimEventDocument, now: dt.datetime
    ) -> ScimEventDocument:
        """Record the event; ScimEventSeen when it is recorded already (the
        unique index decides, so two racing deliveries can't both pass).
        Mongo's TTL index drops expired records."""
        try:
            return await document.insert()
        except DuplicateKeyError:
            raise ScimEventSeen(document.event_key)

    @write_op
    async def release(self, event_key: str) -> int:
        """Forget an event whose processing failed, so Polis's retry is
        applied instead of being taken for a duplicate."""
        result = await ScimEventDocument.find({"event_key": event_key}).delete()
        return result.deleted_count if result else 0
