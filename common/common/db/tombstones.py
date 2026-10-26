"""Deletion tombstones: which ids were deleted, in which store, and when.

While 4.0 wrote both stores, a row could exist on one side only for two
opposite reasons: it was written there and its copy to the other side failed
or had not been backfilled yet, or it was deleted on the other side and its
mirror delete failed. ``reconcile`` used to treat every such row as the first
case and copy it back, so a deleted response, deletion request or account
could come back after a reconcile. A tombstone tells the two apart.

Every Postgres delete records one in the same transaction
(:class:`common.records.repository.RecordRepository`'s delete helpers write
``<schema>.deletion_tombstones``, :func:`record_postgres`), so that the import
from 4.0 (``python -m <service>.migrate``) still never brings a deleted record
back. The Mongo side (a ``deletion_tombstones`` collection a 4.0 stack wrote)
is only read.

A tombstone holds only the collection name, the id and the time of the
delete: no document content and no personal data. A copy is a *deletion
victim* when a tombstone for its id, from either store, is newer than the
copy's ``updated_at`` (:func:`is_victim`): a document created again under the
same id after the delete (ids derived from a relation are) is newer and so not
a victim. ``verify`` counts the victims still present as ``tombstoned``, and
``reconcile`` never copies a victim: it deletes a victim that exists on one
side only and reports one present on both.

Times are compared at millisecond precision, as Mongo keeps milliseconds where
Postgres keeps microseconds. Tombstone times are stored truncated as well.

Retention: :data:`RETENTION_DAYS`, long enough for the import and the time a
Mongo archive is kept. Postgres ones are pruned, a bounded batch at a time,
every :data:`PRUNE_EVERY` deletes a process records (after the delete
committed, in a transaction of its own) and at the end of each ``reconcile``.
The ``deletion_tombstones`` tables go with the Mongo decommission.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional

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
CHUNK = 1000


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


_recorded: dict[str, int] = {}
_pruned_at: dict[str, int] = {}


def prune_due(schema: str) -> bool:
    """Whether this process has recorded :data:`PRUNE_EVERY` deletes in
    ``schema`` since it last pruned (and so should prune now). The caller
    prunes after the delete committed, in a transaction of its own, so a
    delete's transaction never carries pruning work or its locks."""
    if _recorded.get(schema, 0) - _pruned_at.get(schema, 0) < PRUNE_EVERY:
        return False
    _pruned_at[schema] = _recorded[schema]
    return True


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


# -- Mongo (the 4.0 archive, read by the import) ---------------------------------
def mongo_tombstones(database):
    """The ``deletion_tombstones`` collection a 4.0 stack recorded its Mongo
    deletes in; only read, never written, by 4.1."""
    return database[COLLECTION]
