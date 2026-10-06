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


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def checked_retention(
    kind: Any, value: Any, today: dt.date
) -> Tuple[Optional[ResponseRetentionType], Optional[str]]:
    """A retention setting as it may be stored: ``(type, value)``, the value
    normalised (``days`` a whole number, ``date`` YYYY-MM-DD, ``forever`` and
    no type without one).

    Raises ``ValueError`` (with a message for the creator) when the period
    can't be applied: days out of range, an unreadable date, or a date that
    isn't after ``today`` (on the Postgres path a past end deletes each new
    submission almost at once). Every path that stores the setting goes
    through here: the settings patch, and form create and update.
    """
    if _blank(kind):
        if not _blank(value):
            raise ValueError("Choose how long answers are kept.")
        return None, None
    try:
        kind = ResponseRetentionType(getattr(kind, "value", kind))
    except ValueError:
        raise ValueError("Choose how long answers are kept.")
    if kind == ResponseRetentionType.FOREVER:
        return kind, None
    if kind == ResponseRetentionType.DAYS:
        days = retention_days(value)
        if days is None:
            raise ValueError(f"Keep answers for 1 to {MAX_RETENTION_DAYS} days.")
        return kind, str(days)
    day = retention_date(value)
    if day is None or day <= today:
        raise ValueError("Choose a date in the future to keep answers until.")
    return kind, day.isoformat()
