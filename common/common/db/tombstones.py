"""Deletion tombstones: which ids were deleted, in which store, and when.

While both stores are written, a row can exist on one side only for two
opposite reasons: it was written there and its copy to the other side failed
or has not been backfilled yet, or it was deleted on the other side and its
mirror delete failed. ``reconcile`` used to treat every such row as the
first case and copy it back, so a deleted response, deletion request or
account could come back after a reconcile. A tombstone tells the two apart.

Every delete records one, in the store that deletes, in all write modes:

* **Postgres** — :class:`common.db.pg_repository.PostgresRepositoryBase`'s
  delete helpers write ``<schema>.deletion_tombstones`` in the same
  transaction as the delete (:func:`record_postgres`);
* **Mongo** — every document class initialised by
  :func:`common.db.mongo.init_documents` gets a collection whose deletes
  (``delete_one``, ``delete_many``, ``find_one_and_delete``, so also Beanie's
  ``document.delete()`` and ``find(...).delete()``) first read the matching
  ids, record them in the ``deletion_tombstones`` collection, and then delete
  exactly those ids (:class:`TombstoningCollection`).

A tombstone holds only the collection name, the id and the time of the
delete (the write clock, :func:`common.clock.utcnow`): no document content
and no personal data. A copy is a *deletion victim* when a tombstone for its
id, from either store, is newer than the copy's ``updated_at``
(:func:`is_victim`): a document created again under the same id after the
delete (ids derived from a relation are) is newer and so not a victim.
``verify`` counts the victims still present as ``tombstoned``, and
``reconcile`` never copies a victim: it deletes a victim that exists on one
side only and reports one present on both.

Times are compared at millisecond precision: a routed write stamps both
stores with one clock reading, and Mongo keeps milliseconds where Postgres
keeps microseconds, so a record deleted and written again in the same write
(relation-derived ids, as a responder group's members) must not look older
than its own tombstone. Tombstone times are stored truncated as well.

Retention: :data:`RETENTION_DAYS`, long enough for the cutover. Mongo expires
its tombstones by a TTL index; Postgres ones are pruned, a bounded batch at a
time, every :data:`PRUNE_EVERY` deletes a process records and at the end of
each ``reconcile``. Both go with the Mongo decommission: drop the
``deletion_tombstones`` tables and the Mongo collection then.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional

from pymongo.errors import BulkWriteError, OperationFailure
from pymongo.results import DeleteResult
from sqlalchemy import TIMESTAMP, Text, column, select, table, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, mapped_column

from common.clock import utcnow

TABLE = "deletion_tombstones"
COLLECTION = TABLE
#: How long a tombstone is kept. Longer than any cutover stage plus the time a
#: Mongo archive is kept, so a copy restored from it is still recognised.
RETENTION_DAYS = 120
#: A process prunes expired Postgres tombstones once per this many deletes.
PRUNE_EVERY = 200
PRUNE_BATCH = 1000
#: Collections whose deletes are not tombstoned (the bookkeeping itself).
NOT_TOMBSTONED = frozenset({COLLECTION, "mirror_write_failures"})
CHUNK = 1000
DUPLICATE_KEY = 11000


class DeletionTombstoneMixin:
    """Columns of ``<schema>.deletion_tombstones``. Concrete class per service:

    class DeletionTombstone(Base, DeletionTombstoneMixin):
        __tablename__ = "deletion_tombstones"
    """

    collection: Mapped[str] = mapped_column(Text, primary_key=True)
    row_id: Mapped[str] = mapped_column(Text, primary_key=True)
    deleted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )


def postgres_table(schema: str):
    """The tombstone table of ``schema``, as a lightweight table construct."""
    return table(
        TABLE,
        column("collection", Text),
        column("row_id", Text),
        column("deleted_at", TIMESTAMP(timezone=True)),
        schema=schema,
    )


def _aware(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def to_ms(value: datetime) -> datetime:
    """``value`` truncated to milliseconds (Mongo's precision)."""
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


def is_victim(deleted_at: Optional[datetime], updated_at: Any) -> bool:
    """Whether a copy last written at ``updated_at`` was deleted at
    ``deleted_at``, compared at millisecond precision (so a copy written in
    the same write as the delete is not a victim). A copy without a usable
    ``updated_at`` counts as older than any tombstone."""
    if deleted_at is None:
        return False
    written = _aware(updated_at)
    return written is None or to_ms(_aware(deleted_at)) > to_ms(written)


def merge(*tombstones: Mapping[str, datetime]) -> dict[str, datetime]:
    """id -> the latest deleted_at over several stores' tombstones."""
    out: dict[str, datetime] = {}
    for found in tombstones:
        for row_id, deleted_at in found.items():
            at = _aware(deleted_at)
            if at is not None and (row_id not in out or at > out[row_id]):
                out[row_id] = at
    return out


# -- Postgres -----------------------------------------------------------------
async def record_postgres(session, schema: str, collection: str, ids: Iterable[Any]):
    """Record ``ids`` of ``collection`` as deleted now, in ``session``'s
    transaction (so with the delete itself)."""
    ids = [str(i) for i in ids]
    if not ids:
        return
    tombstones = postgres_table(schema)
    at = to_ms(utcnow())
    for start in range(0, len(ids), CHUNK):
        stmt = pg_insert(tombstones).values(
            [
                {"collection": collection, "row_id": i, "deleted_at": at}
                for i in ids[start : start + CHUNK]
            ]
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["collection", "row_id"],
                set_={"deleted_at": stmt.excluded.deleted_at},
            )
        )
    _recorded[schema] = _recorded.get(schema, 0) + 1
    if _recorded[schema] % PRUNE_EVERY == 0:
        await prune_postgres(session, schema)


_recorded: dict[str, int] = {}


async def prune_postgres(
    connection, schema: str, now: Optional[datetime] = None
) -> int:
    """Delete up to :data:`PRUNE_BATCH` Postgres tombstones of ``schema``
    older than the retention; returns how many."""
    cut = (now or datetime.now(timezone.utc)) - timedelta(days=RETENTION_DAYS)
    tombstones = postgres_table(schema)
    oldest = (
        select(tombstones.c.collection, tombstones.c.row_id)
        .where(tombstones.c.deleted_at < cut)
        .limit(PRUNE_BATCH)
    )
    result = await connection.execute(
        tombstones.delete().where(
            tuple_(tombstones.c.collection, tombstones.c.row_id).in_(oldest)
        )
    )
    return int(result.rowcount or 0)


# -- Mongo --------------------------------------------------------------------
def mongo_tombstones(database):
    return database[COLLECTION]


async def record_mongo(database, collection: str, ids: Iterable[Any], session=None):
    """Record ``ids`` of ``collection`` as deleted now. One ``insert_many``
    per chunk; an id already tombstoned (a duplicate key) has its
    ``deleted_at`` moved to now instead."""
    ids = [str(i) for i in ids]
    if not ids:
        return
    at = to_ms(utcnow())
    tombstones = mongo_tombstones(database)
    for start in range(0, len(ids), CHUNK):
        chunk = ids[start : start + CHUNK]
        try:
            await tombstones.insert_many(
                [
                    {
                        "_id": f"{collection}:{i}",
                        "collection": collection,
                        "row_id": i,
                        "deleted_at": at,
                    }
                    for i in chunk
                ],
                ordered=False,
                session=session,
            )
        except BulkWriteError as error:
            errors = error.details.get("writeErrors", [])
            if any(e.get("code") != DUPLICATE_KEY for e in errors):
                raise
            again = [chunk[e["index"]] for e in errors]
            await tombstones.update_many(
                {"_id": {"$in": [f"{collection}:{i}" for i in again]}},
                {"$set": {"deleted_at": at}},
                session=session,
            )


async def ensure_mongo_ttl(database) -> None:
    """Expire Mongo tombstones after :data:`RETENTION_DAYS` (idempotent; an
    index made with another retention is changed in place)."""
    seconds = int(timedelta(days=RETENTION_DAYS).total_seconds())
    try:
        await mongo_tombstones(database).create_index(
            "deleted_at", name="deleted_at_ttl", expireAfterSeconds=seconds
        )
    except OperationFailure as error:
        if error.code not in (85, 86):  # IndexOptionsConflict, IndexKeySpecsConflict
            raise
        await database.command(
            "collMod",
            COLLECTION,
            index={"name": "deleted_at_ttl", "expireAfterSeconds": seconds},
        )


class TombstoningCollection:
    """A pymongo collection whose deletes record a tombstone per deleted id
    before deleting. Everything else is the wrapped collection's."""

    def __init__(self, collection):
        self._collection = collection

    def __getattr__(self, name: str) -> Any:
        return getattr(self._collection, name)

    def __getitem__(self, name: str) -> Any:
        return self._collection[name]

    @property
    def wrapped(self):
        return self._collection

    async def _record(self, ids, session) -> None:
        await record_mongo(
            self._collection.database, self._collection.name, ids, session=session
        )

    async def delete_one(self, filter: Mapping[str, Any], *args, **kwargs):
        session = kwargs.get("session")
        found = await self._collection.find_one(filter, {"_id": 1}, session=session)
        if found is None:
            return DeleteResult({"n": 0, "ok": 1}, True)
        await self._record([found["_id"]], session)
        return await self._collection.delete_one(
            {"$and": [dict(filter), {"_id": found["_id"]}]}, *args, **kwargs
        )

    async def delete_many(self, filter: Mapping[str, Any], *args, **kwargs):
        session = kwargs.get("session")
        ids = [
            d["_id"]
            for d in await self._collection.find(
                filter, {"_id": 1}, session=session
            ).to_list()
        ]
        deleted = 0
        for start in range(0, len(ids), CHUNK):
            chunk = ids[start : start + CHUNK]
            await self._record(chunk, session)
            result = await self._collection.delete_many(
                {"$and": [dict(filter), {"_id": {"$in": chunk}}]}, *args, **kwargs
            )
            deleted += result.deleted_count
        return DeleteResult({"n": deleted, "ok": 1}, True)

    async def find_one_and_delete(self, filter: Mapping[str, Any], *args, **kwargs):
        session = kwargs.get("session")
        found = await self._collection.find_one(
            filter, {"_id": 1}, session=session, sort=kwargs.get("sort")
        )
        if found is None:
            return None
        await self._record([found["_id"]], session)
        return await self._collection.find_one_and_delete(
            {"$and": [dict(filter), {"_id": found["_id"]}]}, *args, **kwargs
        )


def tombstone_deletes(document_models: Iterable[type]) -> None:
    """Give each initialised document class a :class:`TombstoningCollection`."""
    for model in document_models:
        get_settings = getattr(model, "get_settings", None)
        if get_settings is None:
            continue
        settings = get_settings()
        current = getattr(settings, "pymongo_collection", None)
        if current is None or isinstance(current, TombstoningCollection):
            continue
        if settings.name in NOT_TOMBSTONED:
            continue
        settings.pymongo_collection = TombstoningCollection(current)
