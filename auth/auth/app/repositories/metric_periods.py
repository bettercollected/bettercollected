"""Time windows for the user counts of the platform metrics dashboard.

Users are dated by their id: the smallest id minted at a moment bounds a
range on ``id`` (24-hex strings order like the ObjectIds they encode).
"""

import datetime as dt

from common.ids import RecordId


def utc(moment: dt.datetime) -> dt.datetime:
    """``moment`` in UTC (naive means UTC), truncated to the second."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0)


def object_id_at(moment: dt.datetime) -> RecordId:
    """The smallest id minted at ``moment``."""
    return RecordId.from_datetime(utc(moment))
