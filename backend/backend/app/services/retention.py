"""How long a form keeps its answers, as set on the form.

``WorkspaceFormSettings.response_expiration_type`` / ``response_expiration``:
``days`` with a whole number of days, ``date`` with a ``YYYY-MM-DD`` day, or
``forever`` / unset (kept until deleted). The respondent form states this
period in plain words (webapp ``utils/retention.ts``, which reads the settings
with the same rules — keep the two in step), so the server applies it to every
submission itself: a period the form states is a period that is enforced.
"""

import datetime as dt
import re
from typing import Any, Optional, Tuple

from backend.app.services.internal_fields import _get
from common.models.consent import ResponseRetentionType

MAX_RETENTION_DAYS = 3650
_DAYS = re.compile(r"^\d{1,4}$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _type(settings: Any) -> Optional[str]:
    value = _get(settings, "response_expiration_type")
    return getattr(value, "value", value)


def retention_days(value: Any) -> Optional[int]:
    """A valid number of days (1..MAX_RETENTION_DAYS), or None."""
    text = str(value if value is not None else "").strip()
    if not _DAYS.match(text):
        return None
    days = int(text)
    return days if 0 < days <= MAX_RETENTION_DAYS else None


def retention_date(value: Any) -> Optional[dt.date]:
    """The calendar day a ``date`` retention ends on, or None."""
    match = _DAY.match(str(value if value is not None else "").strip())
    if not match:
        return None
    try:
        return dt.date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _iso(moment: dt.datetime) -> str:
    # The format scheduled deletion parses (utils/date_utils.py).
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def submission_expiry(
    settings: Any, now: dt.datetime
) -> Optional[Tuple[str, ResponseRetentionType]]:
    """When a submission made at ``now`` (UTC) expires under the form's
    retention, as ``(expiration, expiration_type)``; None when the form keeps
    answers until they are deleted or its setting is unreadable."""
    retention_type = _type(settings)
    value = _get(settings, "response_expiration")
    if retention_type == ResponseRetentionType.DAYS.value:
        days = retention_days(value)
        if days:
            return _iso(now + dt.timedelta(days=days)), ResponseRetentionType.DAYS
    elif retention_type == ResponseRetentionType.DATE.value:
        day = retention_date(value)
        if day:
            end = dt.datetime(day.year, day.month, day.day)
            return _iso(end), ResponseRetentionType.DATE
    return None
