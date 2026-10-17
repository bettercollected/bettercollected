import datetime as dt
from typing import Optional

from common.configs.mongo_document import MongoDocument
from pydantic import field_validator
from pymongo import IndexModel

IDEMPOTENCY_PENDING = "pending"
IDEMPOTENCY_DONE = "done"


class ApiIdempotencyRecordDocument(MongoDocument):
    """One ``Idempotency-Key`` an API key sent to the public API
    (services/idempotency.py): the request it was first used for and, once
    that finished, its response, replayed to a retry with the same key.

    The id is derived from the API key's id and the client's key, so a key
    is claimed by inserting it. Kept until ``expires_at`` (24 hours)."""

    key_id: str
    # SHA-256 of the method, path and body of the first request
    request_hash: str
    state: str = IDEMPOTENCY_PENDING
    status_code: Optional[int] = None
    # the response body as JSON text, stored and replayed as it was sent
    body: Optional[str] = None
    etag: Optional[str] = None
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "api_idempotency_keys"
        indexes = [
            # Mongo drops a record once it expired; the Postgres twin deletes
            # expired rows whenever it stores a new one
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]
