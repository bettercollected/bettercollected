import datetime as dt

from common.configs.mongo_document import MongoDocument
from pydantic import field_validator
from pymongo import IndexModel


class RateLimitCounterDocument(MongoDocument):
    """Requests one client made in one fixed window (services/rate_limiter.py).

    The id is derived from a keyed hash of the scope, the client and the
    window, so the record names no address. Kept until ``expires_at``, a
    window after its own ended."""

    hits: int = 0
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "rate_limit_counters"
        indexes = [
            # Mongo drops a counter once it expired; the Postgres twin deletes
            # expired rows whenever it starts a new one
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]
