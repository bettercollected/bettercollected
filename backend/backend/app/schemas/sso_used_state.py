import datetime as dt

from common.records import Record
from pydantic import field_validator


class SsoUsedStateDocument(Record):
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
        # nonce_hash is unique; expired records are deleted on each claim
        name = "sso_used_states"
