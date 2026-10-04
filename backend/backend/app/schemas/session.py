import datetime as dt
from typing import Optional

from beanie import Indexed
from pydantic import field_validator
from typing_extensions import Annotated

from backend.app.handlers.database import entity
from common.configs.mongo_document import MongoDocument


@entity
class SessionDocument(MongoDocument):
    """One signed-in browser session: created at every sign-in, named by the
    ``sid`` claim of the tokens issued for it.

    Access tokens are checked without a database read; the refresh path reads
    this document, so revoking it ends the session within one access-token
    lifetime. ``refresh_jti`` is the refresh token currently valid for the
    session (rotated on each explicit refresh); ``previous_refresh_jti`` is the
    one it replaced, accepted for a short grace period after ``rotated_at`` so
    parallel tabs do not trip reuse detection. Any other jti presented for the
    session is a replayed (stolen) token and revokes it.
    """

    user_id: Annotated[str, Indexed()]
    refresh_jti: str
    previous_refresh_jti: Optional[str] = None
    rotated_at: Optional[dt.datetime] = None
    last_refreshed_at: Optional[dt.datetime] = None
    expires_at: dt.datetime
    # proven at sign-in (see common.models.user.User.email_verified)
    email_verified: bool = False
    user_agent: Optional[str] = None
    revoked_at: Optional[dt.datetime] = None
    revoke_reason: Optional[str] = None

    @field_validator(
        "rotated_at", "last_refreshed_at", "expires_at", "revoked_at", mode="after"
    )
    @classmethod
    def _utc(cls, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
        # Mongo hands datetimes back naive (UTC); keep them comparable
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        # native dates (no ISO-string encoders): expiry and revocation compare them
        name = "sessions"
