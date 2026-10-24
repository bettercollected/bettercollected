import datetime as dt
from typing import Optional

from common.records import Record
from pydantic import field_validator

IDEMPOTENCY_PENDING = "pending"
IDEMPOTENCY_DONE = "done"


class ApiIdempotencyRecordDocument(Record):
    """One ``Idempotency-Key`` an API key sent to the public API
    (services/idempotency.py): the request it was first used for and, once
    that finished, a summary of its response, from which a retry with the
    same key is answered.

    The id is derived from the API key's id and the client's key, so a key
    is claimed by inserting it. Kept until ``expires_at`` (24 hours)."""

    # the repository deletes expired records whenever it stores a new one

    key_id: str
    # SHA-256 of the method, path and body of the first request
    request_hash: str
    state: str = IDEMPOTENCY_PENDING
    status_code: Optional[int] = None
    # a small summary of the response (JSON text, capped): the form id and
    # per-op results, or an error or publish body; never a whole form
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
