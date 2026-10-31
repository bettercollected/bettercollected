"""The numbers of the drafts feature, in one place.

Retention: a form keeps a draft ``draft_retention_days`` days after its last
save (default 30, a creator picks 1 to 90), never longer than 90 days after
its first save and never past a fixed retention date of the form itself. The
magic link opens a draft for 7 days at most.

Rate limits are fixed windows counted in the database (shared by every
replica, ``services/rate_limiter.py``); each key is a keyed hash, no address is
stored in a counter.
"""

import datetime as dt
from typing import Any, Optional

DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 90
# a draft never lives longer than this from its first save, however often saved
ABSOLUTE_LIFETIME = dt.timedelta(days=90)
LINK_LIFETIME = dt.timedelta(days=7)

# the encrypted payload (answers, hidden fields, position), serialised JSON
MAX_PAYLOAD_BYTES = 256 * 1024
# live drafts one address may hold on one form
MAX_DRAFTS_PER_ADDRESS = 5
# live anonymous drafts one form may hold in all, and live drafts one account may hold
# (one per form): storage bounds, 409 ``draft_limit`` past them
MAX_ANONYMOUS_DRAFTS_PER_FORM = 2000
MAX_DRAFTS_PER_ACCOUNT = 50

HOUR = 3600
# mails the link: per address and form, per client, per form (one form cannot
# be used to mail the world), per workspace, as (scope, limit, window seconds)
LINK_PER_ADDRESS = ("draft-link-address", 3, HOUR)
LINK_PER_CLIENT = ("draft-link-client", 10, HOUR)
LINK_PER_FORM = ("draft-link-form", 60, HOUR)
# and one workspace, whatever its forms, in all
LINK_PER_WORKSPACE = ("draft-link-workspace", 1000, HOUR)
SAVES_PER_CLIENT = ("draft-save", 120, HOUR)
# opening a draft: every attempt counts, a failed one counts again
OPENS_PER_CLIENT = ("draft-open", 60, HOUR)
OPEN_MISSES_PER_CLIENT = ("draft-open-miss", 10, HOUR)


def normalized_draft_retention_days(value: Any) -> Optional[int]:
    """The draft retention as the settings PATCH stores it: None (no change),
    0 (the default again) or a whole number of days from 1 to 90. Raises
    ValueError for anything else (a 422)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Drafts are kept a whole number of days.")
    if value < 0 or value > MAX_RETENTION_DAYS:
        raise ValueError(
            f"Drafts are kept between {MIN_RETENTION_DAYS} and "
            f"{MAX_RETENTION_DAYS} days (0 is the default of "
            f"{DEFAULT_RETENTION_DAYS})."
        )
    return value


def draft_days(settings: Any) -> int:
    """The days a form keeps a draft: its setting when it is a valid one, else
    the default."""
    value = getattr(settings, "draft_retention_days", None)
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and MIN_RETENTION_DAYS <= value <= MAX_RETENTION_DAYS
    ):
        return value
    return DEFAULT_RETENTION_DAYS


def saving_enabled(settings: Any) -> bool:
    return bool(getattr(settings, "allow_save_draft", None))
