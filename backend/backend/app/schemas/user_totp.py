import datetime as dt
from typing import Optional

from common.records import Record
from pydantic import Field, field_validator

PENDING = "pending"
CONFIRMED = "confirmed"

# how the account proved itself when it added the factor
ENROLLED_RECENT_SIGN_IN = "recent_sign_in"


def _aware(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class UserTotpFactorDocument(Record):
    """The authenticator-app factor of an account (docs/totp.md): one pending
    (being set up) and at most one confirmed. ``secret_sealed`` is the shared
    secret inside a bound, encrypted envelope (``services/mfa/sealing.py``);
    it is never logged, returned after enrolment or shown in ``repr``."""

    user_id: str
    state: str = PENDING
    secret_sealed: str = Field(repr=False)
    confirmed_at: Optional[dt.datetime] = None
    # the newest 30-second step a code was accepted for (replay guard)
    last_used_step: Optional[int] = None
    enrolled_via: Optional[str] = None
    # the second-factor step is refused until then (too many wrong codes)
    locked_until: Optional[dt.datetime] = None
    # locks since the last accepted code: each one lasts longer
    lock_count: int = 0
    # the language of the person's last second-factor use (the first
    # Accept-Language tag), so a notice about their account that someone else
    # caused (a reset) is written in their language, not the caller's
    locale: Optional[str] = None

    @field_validator("confirmed_at", "locked_until", mode="after")
    @classmethod
    def _utc(cls, value):
        return _aware(value)

    class Settings:
        name = "user_totp_factors"


class UserRecoveryCodeDocument(Record):
    """One recovery code: only ``code_hash`` is stored; ``used_at`` marks it
    burned."""

    factor_id: str
    user_id: str
    code_hash: str = Field(repr=False)
    used_at: Optional[dt.datetime] = None

    @field_validator("used_at", mode="after")
    @classmethod
    def _utc(cls, value):
        return _aware(value)

    class Settings:
        name = "user_recovery_codes"
