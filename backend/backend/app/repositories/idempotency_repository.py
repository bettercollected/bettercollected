import datetime as dt
from typing import Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from backend.app.schemas.api_idempotency_record import (
    IDEMPOTENCY_DONE,
    IDEMPOTENCY_PENDING,
    ApiIdempotencyRecordDocument,
)
from common.db.routing import write_op


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class IdempotencyRepository:
    async def find(self, record_id: str) -> Optional[ApiIdempotencyRecordDocument]:
        """The record, unless it expired (Mongo's TTL sweep can lag)."""
        return await ApiIdempotencyRecordDocument.find_one(
            {"_id": ObjectId(record_id), "expires_at": {"$gt": _now()}}
        )

    @write_op
    async def claim(self, record: ApiIdempotencyRecordDocument) -> bool:
        """Store ``record`` unless a live record has its id; True when this
        call stored it. Atomic: of two requests with the same key, one
        claims it."""
        collection = ApiIdempotencyRecordDocument.get_pymongo_collection()
        # an expired record not yet swept gives way to the new one
        await collection.delete_one({"_id": record.id, "expires_at": {"$lte": _now()}})
        try:
            await record.insert()
        except DuplicateKeyError:
            return False
        return True

    @write_op
    async def complete(
        self,
        record_id: str,
        status_code: int,
        body: str,
        etag: Optional[str] = None,
    ) -> None:
        """Keep the response of the request that claimed ``record_id``."""
        await ApiIdempotencyRecordDocument.get_pymongo_collection().update_one(
            {"_id": ObjectId(record_id), "state": IDEMPOTENCY_PENDING},
            {
                "$set": {
                    "state": IDEMPOTENCY_DONE,
                    "status_code": status_code,
                    "body": body,
                    "etag": etag,
                    "updated_at": _now(),
                }
            },
        )

    @write_op
    async def release(self, record_id: str) -> None:
        """Forget a claim whose request failed on our side, so a retry runs."""
        await ApiIdempotencyRecordDocument.get_pymongo_collection().delete_one(
            {"_id": ObjectId(record_id), "state": IDEMPOTENCY_PENDING}
        )
