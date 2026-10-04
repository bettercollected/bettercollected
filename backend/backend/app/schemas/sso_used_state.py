import datetime as dt

from common.configs.mongo_document import MongoDocument
from pydantic import field_validator
from pymongo import IndexModel


class SsoUsedStateDocument(MongoDocument):
    """A single sign-on callback that was accepted, by the hash of its
    browser nonce (docs/sso.md): a state is accepted once. Kept until
    ``expires_at`` (well past the sign-in's own expiry)."""

    nonce_hash: str
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "sso_used_states"
        indexes = [
            IndexModel([("nonce_hash", 1)], unique=True),
            # Mongo drops a record once it expired; the Postgres twin deletes
            # expired rows on each claim
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]
