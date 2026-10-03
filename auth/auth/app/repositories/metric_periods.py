"""Time windows for the user counts of the platform metrics dashboard.

Shared by the Mongo user repository and its Postgres twin so both count the
same users: the smallest ObjectId minted at a moment bounds a range on ``_id``
in Mongo and on ``id`` in Postgres (24-hex strings order like the ObjectIds);
ISO-string timestamps in Mongo are compared at second precision.
"""

import datetime as dt

from beanie import PydanticObjectId


def utc(moment: dt.datetime) -> dt.datetime:
    """``moment`` in UTC (naive means UTC), truncated to the second."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0)


def object_id_at(moment: dt.datetime) -> PydanticObjectId:
    """The smallest ObjectId minted at ``moment``."""
    return PydanticObjectId.from_datetime(utc(moment))


def iso_second(moment: dt.datetime) -> str:
    """``moment`` as the prefix of an ISO timestamp (stored strings are UTC)."""
    return utc(moment).strftime("%Y-%m-%dT%H:%M:%S")
