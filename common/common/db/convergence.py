"""Bring the mirror's copy of what a routed write touched in line with the primary.

Two routed writes to the same document can reach the mirror in the opposite
order to the one they reached the primary in: write A reaches the primary,
write B reaches the primary and then the mirror, and only then does A's
mirror write land. Whether the mirror re-executes the call or stores the
document the primary returned, it then keeps A, the older version, while the
primary holds B. Nothing reports it until ``verify`` runs, and a read switch
in between would serve the older version.

So after its mirror write, every routed write runs :func:`converge` over the
rows it touched: it reads the primary's current copy of each and stores it on
the mirror (or deletes the mirror's copy when the primary no longer has one),
then reads both again, until they agree. The last write to reach a document's
mirror is always followed by such a check of that document, so the mirror
ends with what the primary holds, whatever order the writes arrived in. A
version clock would not do: it orders only the writes that move a stored
timestamp, it needs a column in every table, and the primary itself applies
concurrent writes in an order no clock records.

What a write touched is collected on the Postgres side, which takes part in
every mirrored write (as primary under ``postgres_primary_dual``, as mirror
under ``dual``): :class:`common.db.pg_repository.PostgresRepositoryBase`
reports the ids it upserts or deletes through :func:`touch` while a routed
write's :func:`collecting` block is open. A copy is compared by its checksum
(:func:`common.db.canonical.checksum`), the same comparison ``verify`` makes.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional

from bson import ObjectId
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum, from_canonical_document
from common.db.flags import ReadSource

#: Copy-and-check rounds before a document counts as diverged (a mirror failure).
ROUNDS = 3
#: Ids per read/write batch.
CHUNK = 500

_OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")


class Diverged(RuntimeError):
    """The primary kept changing while its copy was brought to the mirror."""


@dataclass
class TouchedTable:
    """The rows of one table a routed write touched, and how to reach both copies."""

    row: Any  # the BaseRow class
    sessions: Any  # async_sessionmaker of the Postgres store
    mongo_collection: Callable[[], Any]  # the Mongo collection (resolved lazily)
    ids: set = field(default_factory=set)


_current: ContextVar[Optional[dict]] = ContextVar("bc_touched_rows", default=None)


@contextmanager
def collecting() -> Iterator[dict]:
    """Collect the rows the enclosed routed write touches (row class ->
    :class:`TouchedTable`). Each routed write opens its own block, so the
    rows of a routed write nested in it are converged by that write, not
    this one."""
    touched: dict = {}
    token = _current.set(touched)
    try:
        yield touched
    finally:
        _current.reset(token)


def touch(
    row: Any,
    ids: Iterable[Any],
    *,
    sessions: Any,
    mongo_collection: Callable[[], Any],
) -> None:
    """Record that the current routed write wrote (or deleted) ``ids`` of
    ``row``'s table. Outside a routed write this does nothing."""
    touched = _current.get()
    if touched is None:
        return
    entry = touched.get(row)
    if entry is None:
        entry = touched[row] = TouchedTable(row, sessions, mongo_collection)
    entry.ids.update(str(i) for i in ids)


def touched_ids(touched: Mapping[Any, TouchedTable]) -> list[str]:
    return sorted({i for entry in touched.values() for i in entry.ids})


def _other(store: ReadSource) -> ReadSource:
    return ReadSource.POSTGRES if store is ReadSource.MONGO else ReadSource.MONGO


async def converge(
    touched: Mapping[Any, TouchedTable], primary: ReadSource, *, rounds: int = ROUNDS
) -> int:
    """Make the mirror's copy of every touched row equal the primary's.
    Returns how many mirror copies were rewritten (0 when the mirror write
    had already left them equal); raises :class:`Diverged` when a row still
    differs after ``rounds`` copies."""
    rewritten = 0
    for entry in touched.values():
        ids = sorted(i for i in entry.ids if _OBJECT_ID.match(i))
        for start in range(0, len(ids), CHUNK):
            rewritten += await _converge_ids(
                entry, ids[start : start + CHUNK], primary, rounds
            )
    return rewritten


async def _converge_ids(
    entry: TouchedTable, ids: list[str], primary: ReadSource, rounds: int
) -> int:
    mirror = _other(primary)
    rewritten = 0
    for attempt in range(rounds + 1):
        # the primary first: a copy read from it is never older than the
        # mirror's copy read after it
        source = await _read(entry, ids, primary)
        target = await _read(entry, ids, mirror)
        ids = [
            i
            for i in ids
            if (source.get(i) or (None,))[0] != (target.get(i) or (None,))[0]
        ]
        if not ids:
            return rewritten
        if attempt == rounds:
            break
        await _write(entry, {i: source.get(i) for i in ids}, mirror)
        rewritten += len(ids)
    raise Diverged(
        f"{entry.row.mongo_collection()}: {len(ids)} document(s) still differ "
        f"after {rounds} copies"
    )


async def _read(
    entry: TouchedTable, ids: list[str], store: ReadSource
) -> dict[str, tuple[str, Any]]:
    """id -> (checksum, copy) for the ids present in ``store``; the copy is
    the canonical ``doc`` from Postgres, the raw document from Mongo."""
    if store is ReadSource.POSTGRES:
        row = entry.row
        async with entry.sessions() as session:
            rows = (
                await session.execute(
                    select(row.id, row.bc_checksum, row.doc).where(row.id.in_(ids))
                )
            ).all()
        return {r[0]: (r[1], r[2]) for r in rows}
    collection = entry.mongo_collection()
    found = await collection.find(
        {"_id": {"$in": [ObjectId(i) for i in ids]}}
    ).to_list()
    return {str(d["_id"]): (checksum(canonical_document(d)), d) for d in found}


def _timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


async def _write(
    entry: TouchedTable,
    copies: Mapping[str, Optional[tuple[str, Any]]],
    store: ReadSource,
) -> None:
    """Store each copy on ``store``; ``None`` deletes the id there."""
    absent = [i for i, copy in copies.items() if copy is None]
    present = {i: copy[1] for i, copy in copies.items() if copy is not None}
    if store is ReadSource.MONGO:
        collection = entry.mongo_collection()
        for doc in present.values():
            document = from_canonical_document(doc)
            await collection.replace_one(
                {"_id": document["_id"]}, document, upsert=True
            )
        if absent:
            await collection.delete_many(
                {"_id": {"$in": [ObjectId(i) for i in absent]}}
            )
        return
    row = entry.row
    async with entry.sessions() as session, session.begin():
        now = datetime.now(timezone.utc)
        for raw in present.values():
            doc = canonical_document(raw)
            stmt = pg_insert(row.__table__).values(
                {
                    "id": str(raw["_id"]),
                    "doc": doc,
                    "created_at": _timestamp(raw.get("created_at")) or now,
                    "updated_at": _timestamp(raw.get("updated_at")) or now,
                    "_bc_source": SOURCE_APP,
                    "_bc_checksum": checksum(doc),
                }
            )
            excluded = stmt.excluded
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        name: excluded[name]
                        for name in (
                            "doc",
                            "created_at",
                            "updated_at",
                            "_bc_source",
                            "_bc_checksum",
                        )
                    },
                )
            )
        if absent:
            await session.execute(delete(row).where(row.id.in_(absent)))
