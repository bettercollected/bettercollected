import datetime as dt

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from common.db.routing import write_op


class RateLimitRepository:
    @write_op
    async def hit(self, counter_id: str, expires_at: dt.datetime) -> int:
        """Count one request on the counter ``counter_id`` (24 hex characters),
        creating it to expire at ``expires_at``; returns the count including
        this request. Atomic, so requests reaching several replicas at once
        are all counted."""
        now = dt.datetime.now(dt.timezone.utc)
        collection = RateLimitCounterDocument.get_pymongo_collection()
        for attempt in range(2):
            try:
                counter = await collection.find_one_and_update(
                    {"_id": ObjectId(counter_id)},
                    {
                        "$inc": {"hits": 1},
                        "$set": {"updated_at": now},
                        "$setOnInsert": {"expires_at": expires_at, "created_at": now},
                    },
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                    projection={"hits": 1},
                )
                return int(counter["hits"])
            except DuplicateKeyError:
                # two first requests raced on the upsert: the loser's retry
                # finds the counter and increments it
                if attempt:
                    raise
        raise AssertionError("unreachable")
