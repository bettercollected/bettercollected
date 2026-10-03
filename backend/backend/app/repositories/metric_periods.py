"""Time windows for the platform metrics counts (admin dashboard).

Shared by the Mongo repositories and their Postgres twins so both stores count
the same documents. Collections whose ``created_at`` is missing on old
documents are dated by their ObjectId: the smallest ObjectId minted at a
moment bounds a range on ``_id`` in Mongo and on ``id`` in Postgres, where the
24-hex strings order exactly like the ObjectIds. Responses are dated by
``created_at`` (the submission time; an imported response's ObjectId is the
import time), which Mongo stores as an ISO string: it is compared at second
precision against ``iso_second``, the Postgres spine column against ``utc``.
"""

import datetime as dt
from typing import Any, Dict, List, Optional, Sequence

from beanie import PydanticObjectId
from sqlalchemy import and_, func, select


def utc(moment: dt.datetime) -> dt.datetime:
    """``moment`` in UTC (naive means UTC), truncated to the second."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0)


def object_id_at(moment: dt.datetime) -> PydanticObjectId:
    """The smallest ObjectId minted at ``moment``."""
    return PydanticObjectId.from_datetime(utc(moment))


def iso_second(moment: dt.datetime) -> str:
    """``moment`` as the prefix of an ISO timestamp, for comparing the ISO
    strings Mongo stores (with or without fraction and offset, all UTC)."""
    return utc(moment).strftime("%Y-%m-%dT%H:%M:%S")


async def mongo_counts_per_period(
    document: Any,
    field: str,
    bounds: Sequence[Any],
    match: Optional[Dict[str, Any]] = None,
) -> List[int]:
    """Documents of ``document`` per period [bounds[i], bounds[i+1]) of
    ``field``; one count per period, oldest first."""
    if len(bounds) < 2:
        return []
    query = {**(match or {}), field: {"$gte": bounds[0], "$lt": bounds[-1]}}
    rows = (
        await document.find(query)
        .aggregate([{"$bucket": {"groupBy": f"${field}", "boundaries": list(bounds)}}])
        .to_list()
    )
    counts = {str(row["_id"]): row["count"] for row in rows}
    return [counts.get(str(lower), 0) for lower in bounds[:-1]]


async def postgres_counts_per_period(
    repository: Any, column: Any, bounds: Sequence[Any], *where: Any
) -> List[int]:
    """The twin of :func:`mongo_counts_per_period`: one filtered count per
    period of ``column`` in a single scan of the repository's table."""
    if len(bounds) < 2:
        return []
    periods = [
        func.count().filter(and_(column >= lower, column < upper))
        for lower, upper in zip(bounds[:-1], bounds[1:])
    ]
    async with repository._session() as session:
        row = (
            await session.execute(
                select(*periods)
                .select_from(repository.row)
                .where(column >= bounds[0], column < bounds[-1], *where)
            )
        ).one()
    return list(row)
