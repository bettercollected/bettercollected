import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId
from beanie.odm.queries.update import UpdateResponse

from backend.app.schemas.session import SessionDocument
from common.db.routing import write_op


def _oid(session_id) -> Optional[PydanticObjectId]:
    try:
        return PydanticObjectId(session_id)
    except Exception:  # noqa: BLE001 — not an ObjectId: no such session
        return None


class SessionRepository:
    @write_op
    async def save(self, document: SessionDocument) -> SessionDocument:
        return await document.save()

    async def get(self, session_id: str) -> Optional[SessionDocument]:
        oid = _oid(session_id)
        if oid is None:
            return None
        return await SessionDocument.find_one({"_id": oid})

    async def list_active_by_user(self, user_id: str) -> List[SessionDocument]:
        """The user's sessions that are not revoked, newest first (expired ones
        included: the caller decides what to show)."""
        return (
            await SessionDocument.find({"user_id": user_id, "revoked_at": None})
            .sort([("created_at", -1), ("_id", -1)])
            .to_list()
        )

    @write_op(replay=True)
    async def rotate(
        self,
        session_id: str,
        expected_jti: str,
        new_jti: str,
        now: dt.datetime,
        expires_at: dt.datetime,
    ) -> Optional[SessionDocument]:
        """Replace the refresh token only if ``expected_jti`` is still the
        current one and the session is live (compare-and-set). Returns the
        updated session, or None when another request rotated it first or it
        was revoked."""
        oid = _oid(session_id)
        if oid is None:
            return None
        return await SessionDocument.find_one(
            {"_id": oid, "refresh_jti": expected_jti, "revoked_at": None}
        ).update(
            {
                "$set": {
                    "refresh_jti": new_jti,
                    "previous_refresh_jti": expected_jti,
                    "rotated_at": now,
                    "last_refreshed_at": now,
                    "expires_at": expires_at,
                    "updated_at": now,
                }
            },
            response_type=UpdateResponse.NEW_DOCUMENT,
        )

    @write_op
    async def touch(self, session_id: str, now: dt.datetime) -> int:
        oid = _oid(session_id)
        if oid is None:
            return 0
        result = await SessionDocument.find_one(
            {"_id": oid, "revoked_at": None}
        ).update({"$set": {"last_refreshed_at": now, "updated_at": now}})
        # matched, not modified: a touch within the same millisecond counts
        return result.matched_count if result else 0

    @write_op
    async def revoke(self, session_id: str, reason: str, now: dt.datetime) -> int:
        """Revoke one live session; 1 when it was revoked by this call."""
        oid = _oid(session_id)
        if oid is None:
            return 0
        result = await SessionDocument.find_one(
            {"_id": oid, "revoked_at": None}
        ).update(
            {"$set": {"revoked_at": now, "revoke_reason": reason, "updated_at": now}}
        )
        return result.modified_count if result else 0

    @write_op
    async def delete_expired(self, now: dt.datetime) -> int:
        result = await SessionDocument.find({"expires_at": {"$lte": now}}).delete()
        return result.deleted_count if result else 0

    @write_op
    async def delete_all_for_user(self, user_id: str) -> int:
        result = await SessionDocument.find({"user_id": user_id}).delete()
        return result.deleted_count if result else 0

    @write_op
    async def revoke_all_for_user(
        self,
        user_id: str,
        reason: str,
        now: dt.datetime,
        except_session_id: Optional[str] = None,
    ) -> int:
        """Revoke every live session of the user, but ``except_session_id``."""
        query = {"user_id": user_id, "revoked_at": None}
        keep = _oid(except_session_id) if except_session_id else None
        if keep is not None:
            query["_id"] = {"$ne": keep}
        result = await SessionDocument.find(query).update(
            {"$set": {"revoked_at": now, "revoke_reason": reason, "updated_at": now}}
        )
        return result.modified_count if result else 0
