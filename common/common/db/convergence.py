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

import asyncio
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
#: A routed write that touched more rows than this (a bulk delete) is not
#: converged: the reads would outlast the mirror timeout; ``verify`` covers it.
MAX_CONVERGED_IDS = 500

_OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")


class Diverged(RuntimeError):
    """The primary kept changing while its copy was brought to the mirror."""


class CopyUnverified(Diverged):
    """A copy was written to the mirror (or its write was cut off by the
    overall cap) but could not be checked afterwards: the mirror may hold a
    copy made from a read that was already stale. Its outbox entry is kept
    open until a clean full ``verify`` (``reconcile`` alone never resolves
    it), so the cutover's verify step must show the stores agree."""


@dataclass
class TouchedTable:
    """The rows of one table a routed write touched, and how to reach both copies."""

    row: Any  # the BaseRow class
    sessions: Any  # async_sessionmaker of the Postgres store
    mongo_collection: Callable[[], Any]  # the Mongo collection (resolved lazily)
    ids: set = field(default_factory=set)
    ttl: Optional[tuple] = None  # (field, seconds) when Mongo expires the collection


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


def active() -> bool:
    """Whether a routed write is collecting the rows it touches."""
    return _current.get() is not None


def touch(
    row: Any,
    ids: Iterable[Any],
    *,
    sessions: Any,
    mongo_collection: Callable[[], Any],
    ttl: Optional[tuple] = None,
) -> None:
    """Record that the current routed write wrote (or deleted) ``ids`` of
    ``row``'s table. Outside a routed write this does nothing."""
    touched = _current.get()
    if touched is None:
        return
    entry = touched.get(row)
    if entry is None:
        entry = touched[row] = TouchedTable(row, sessions, mongo_collection, ttl=ttl)
    entry.ids.update(str(i) for i in ids)


def ttl_of(document_cls: Any) -> Optional[tuple[str, int]]:
    """(field, seconds) of the TTL index a Beanie document class declares,
    or None. Mongo drops such documents on its own schedule and the twins
    drop expired rows when they write, so the two stores disagree about an
    expired row for a while: convergence treats an expired copy as absent."""
    if document_cls is None:
        return None
    get_settings = getattr(document_cls, "get_settings", None)
    try:
        indexes = get_settings().indexes if get_settings else None
    except Exception:  # noqa: BLE001 — not initialised: no settings to read
        indexes = getattr(getattr(document_cls, "Settings", None), "indexes", None)
    for index in indexes or ():
        index = getattr(index, "index", index)  # Beanie wraps IndexModel
        spec = getattr(index, "document", None)
        if isinstance(spec, Mapping) and "expireAfterSeconds" in spec:
            keys = list(spec.get("key", {}))
            if len(keys) == 1:
                return keys[0], int(spec["expireAfterSeconds"])
    return None


def _expired(document: Mapping[str, Any], ttl: Optional[tuple], now: datetime) -> bool:
    if ttl is None:
        return False
    field_name, seconds = ttl
    at = _timestamp(document.get(field_name))
    return at is not None and at + timedelta(seconds=seconds) <= now


def touched_ids(touched: Mapping[Any, TouchedTable]) -> list[str]:
    return sorted({i for entry in touched.values() for i in entry.ids})


def _other(store: ReadSource) -> ReadSource:
    return ReadSource.POSTGRES if store is ReadSource.MONGO else ReadSource.MONGO


async def converge(
    touched: Mapping[Any, TouchedTable],
    primary: ReadSource,
    *,
    rounds: Optional[int] = None,
    deadline: Optional[float] = None,
    read_timeout: Optional[float] = None,
    cap: Optional[float] = None,
) -> int:
    """Make the mirror's copy of every touched row equal the primary's.

    Returns how many mirror copies were rewritten (0 when the mirror write
    had already left them equal). Raises :class:`Diverged` when a row still
    differs after ``rounds`` copies or once ``deadline`` (a
    ``time.monotonic()`` reading) has passed. The deadline is checked before
    each copy, never in the middle of one, so every copy is followed by its
    re-check; and whenever the loop stops early, a mirror copy whose row the
    primary no longer holds is still deleted, since a delete cannot bring
    data back. A read that fails (or outlasts ``read_timeout``) raises at
    once and changes nothing.

    ``cap`` (a ``time.monotonic()`` reading after ``deadline``) bounds the
    whole step, writes included, so a hung store cannot stall the request:
    a write still running at the cap is cut off, and the re-check still runs
    (bounded by ``read_timeout``). :class:`CopyUnverified` is raised when a
    write was cut off (even if the re-check then finds the stores alike: the
    write may still land) and when anything fails after a copy was made.
    """
    rounds = ROUNDS if rounds is None else rounds
    rewritten = 0
    for entry in touched.values():
        ids = sorted(i for i in entry.ids if _OBJECT_ID.match(i))
        for start in range(0, len(ids), CHUNK):
            rewritten += await _converge_ids(
                entry,
                ids[start : start + CHUNK],
                primary,
                rounds,
                deadline,
                read_timeout,
                cap,
            )
    return rewritten


async def _converge_ids(
    entry: TouchedTable,
    ids: list[str],
    primary: ReadSource,
    rounds: int,
    deadline: Optional[float],
    read_timeout: Optional[float],
    cap: Optional[float],
) -> int:
    mirror = _other(primary)
    name = entry.row.mongo_collection()
    copied = False  # a copy reached (or may have reached) the mirror

    async def read(store):
        return await asyncio.wait_for(_read(entry, ids, store), timeout=read_timeout)

    async def write(copies) -> bool:
        """The copy, cut off at ``cap`` (then: whether it landed is unknown)."""
        nonlocal copied
        copied = True
        if cap is None:
            await _write(entry, copies, mirror)
            return True
        remaining = cap - time.monotonic()
        if remaining > 0:
            try:
                await asyncio.wait_for(_write(entry, copies, mirror), timeout=remaining)
                return True
            except asyncio.TimeoutError:
                pass
        return False

    rewritten = 0
    attempt = 0
    capped = False

    async def rounds_of_copies() -> int:
        nonlocal ids, rewritten, attempt, capped
        while True:
            # the primary first: a copy read from it is never older than the
            # mirror's copy read after it
            source = await read(primary)
            target = await read(mirror)
            ids = [
                i
                for i in ids
                if (source.get(i) or (None,))[0] != (target.get(i) or (None,))[0]
            ]
            if not ids:
                return rewritten
            now = time.monotonic()
            out_of_time = capped or (deadline is not None and now >= deadline)
            if attempt >= rounds or out_of_time:
                # stop copying, but never leave a copy of a row the primary no
                # longer holds: deleting it cannot bring data back
                gone = {i: None for i in ids if i not in source}
                if gone:
                    if cap is not None and now >= cap:
                        # past the cap: the delete gets the read's bound
                        await asyncio.wait_for(
                            _write(entry, gone, mirror), timeout=read_timeout
                        )
                    elif not await write(gone):
                        raise CopyUnverified(f"{name}: a delete was cut off by the cap")
                    rewritten += len(gone)
                left = [i for i in ids if i in source]
                if not left:
                    return rewritten
                if capped:
                    raise CopyUnverified(
                        f"{name}: {len(left)} document(s) still differ after a copy "
                        "was cut off by the cap"
                    )
                why = "the mirror timeout passed" if out_of_time else f"{rounds} copies"
                raise Diverged(
                    f"{name}: {len(left)} document(s) still differ after {why}"
                )
            if not await write({i: source.get(i) for i in ids}):
                capped = True  # re-check what landed, then stop
            rewritten += len(ids)
            attempt += 1

    try:
        done = await rounds_of_copies()
    except Diverged:
        raise  # the stores were read after the last copy: what differs is known
    except Exception as exc:  # noqa: BLE001 — re-raised, marked once a copy was made
        if copied:
            raise CopyUnverified(
                f"{name}: {type(exc).__name__} after a copy; verify must show these "
                "documents clean"
            ) from exc
        raise
    if capped:
        # the stores look alike now, but the cut-off write may still land
        raise CopyUnverified(
            f"{name}: a copy was cut off by the cap and may still land; verify must "
            "show these documents clean"
        )
    return done


async def _read(
    entry: TouchedTable, ids: list[str], store: ReadSource
) -> dict[str, tuple[str, Any]]:
    """id -> (checksum, copy) for the ids present in ``store``; the copy is
    the canonical ``doc`` from Postgres, the raw document from Mongo. An
    expired copy (a collection Mongo expires by TTL) counts as absent."""
    now = datetime.now(timezone.utc)
    if store is ReadSource.POSTGRES:
        row = entry.row
        async with entry.sessions() as session:
            rows = (
                await session.execute(
                    select(row.id, row.bc_checksum, row.doc).where(row.id.in_(ids))
                )
            ).all()
        return {
            r[0]: (r[1], r[2])
            for r in rows
            if not _expired(from_canonical_document(r[2]), entry.ttl, now)
        }
    collection = entry.mongo_collection()
    found = await collection.find(
        {"_id": {"$in": [ObjectId(i) for i in ids]}}
    ).to_list()
    return {
        str(d["_id"]): (checksum(canonical_document(d)), d)
        for d in found
        if not _expired(d, entry.ttl, now)
    }


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
