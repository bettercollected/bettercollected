"""Backfill, verify, reconcile, status — the engine behind the per-service CLIs.

No-hang guarantees (plans/postgres-consolidation.md §5): each Mongo batch is a
fresh ``find({_id: {$gt: last}}).sort(_id).limit(n)``; each Postgres batch is
one short transaction on a connection with statement/lock/idle timeouts; the
batch size adapts (halve when a batch is slow, grow when fast); a time budget
stops at the next checkpoint; the checkpoint is written after the batch
commits; a heartbeat line per batch; an advisory lock plus the checkpoint's
heartbeat refuse a second concurrent run.

Idempotency: ``INSERT … ON CONFLICT (id) DO UPDATE … WHERE _bc_source =
'backfill'`` — a row the application wrote is never overwritten by backfill.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Optional

from bson import ObjectId
from pymongo import AsyncMongoClient
from sqlalchemy import Table, and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from common.db import tombstones
from common.db.base import SOURCE_APP, SOURCE_BACKFILL
from common.db.canonical import canonical_document, checksum, from_canonical_document
from common.db.engine import DatabaseSettings, make_engine
from common.db.groups import SERVICE_GROUPS
from common.db.marker import (
    COMBINE_WINDOW,
    MARKER_TABLE,
    SCOPE_GROUP,
    SCOPE_SERVICE,
    MarkerInfo,
    migration_verified,
)
from common.db.migrate.progress import (
    STATE_DONE,
    STATE_ERROR,
    STATE_PAUSED,
    STATE_RUNNING,
)

logger = logging.getLogger("bettercollected.migrate")

OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")
SPINE_PATH = re.compile(r"doc\s*->\s*'([^']+)'((?:\s*->\s*'[^']+')*)")
STALLED_AFTER_S = 300
MIN_BATCH, MAX_BATCH = 25, 2000
SLOW_BATCH_S, FAST_BATCH_S = 20.0, 2.0
MISSING = object()  # no copy in that store


@dataclass
class Target:
    """What one service's CLI migrates."""

    schema: str
    tables: Mapping[str, Table]  # mongo collection -> its table
    progress: Table
    mongo_uri: str
    mongo_db: str
    database_url: str
    application_name: str = "bettercollected-migrate"
    extras: Mapping[str, Callable[..., Any]] = field(default_factory=dict)
    service: str = ""  # backend | auth | google (common.db.groups.SERVICE_GROUPS)
    # mongo collection -> repository group; a collection not listed belongs to
    # a group named after the service (auth and google have one group each)
    groups: Mapping[str, str] = field(default_factory=dict)
    marker: Optional[Table] = None  # <schema>.store_migration
    code_version: str = ""

    def group_of(self, collection: str) -> str:
        return self.groups.get(collection) or self.service or self.schema

    def group_names(self) -> list[str]:
        """The groups that have collections: in the service's declared order
        (``SERVICE_GROUPS``), then any other in the order collections are listed."""
        names: list[str] = []
        for collection in self.tables:
            group = self.group_of(collection)
            if group not in names:
                names.append(group)
        declared = list(SERVICE_GROUPS.get(self.service, ()))
        return sorted(
            names,
            key=lambda g: declared.index(g) if g in declared else len(declared),
        )

    def collections_of(self, group: str) -> list[str]:
        return [c for c in self.tables if self.group_of(c) == group]


@dataclass
class CollectionReport:
    collection: str
    mongo: int = 0
    postgres: int = 0
    missing_in_postgres: int = 0
    missing_in_mongo: int = 0
    mismatched: int = 0
    drifted: int = 0  # tier 3: row → document round-trip differs from Mongo
    # copies still present (either store) of records deleted after they were
    # last written (common.db.tombstones)
    tombstoned: int = 0
    invalid_ids: int = 0
    duplicates: int = 0
    samples: dict = field(
        default_factory=lambda: {
            "missing_in_postgres": [],
            "missing_in_mongo": [],
            "mismatched": [],
            "drifted": [],
            "tombstoned": [],
        }
    )

    @property
    def clean(self) -> bool:
        return not (
            self.missing_in_postgres
            or self.missing_in_mongo
            or self.mismatched
            or self.drifted
            or self.tombstoned
        )

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def is_object_id(value: Any) -> bool:
    return isinstance(value, ObjectId) or (
        isinstance(value, str) and bool(OBJECT_ID.match(value))
    )


def timestamp_of(value: Any) -> Optional[datetime]:
    """created_at/updated_at as stored by Beanie: a datetime or an ISO string."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def row_from_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Column values for a Mongo document, as a backfilled row."""
    doc = canonical_document(document)
    now = datetime.now(timezone.utc)
    return {
        "id": str(document["_id"]),
        "doc": doc,
        "created_at": timestamp_of(document.get("created_at")) or now,
        "updated_at": timestamp_of(document.get("updated_at")) or now,
        "_bc_source": SOURCE_BACKFILL,
        "_bc_checksum": checksum(doc),
    }


def spine_paths(table: Table) -> dict[str, list[str]]:
    """column name -> document path, parsed from the GENERATED expression."""
    paths: dict[str, list[str]] = {}
    for column in table.columns:
        computed = getattr(column, "computed", None)
        if computed is None:
            continue
        m = SPINE_PATH.search(str(computed.sqltext))
        if m:
            paths[column.name] = [m.group(1), *re.findall(r"'([^']+)'", m.group(2))]
    return paths


def unique_key_paths(table: Table) -> list[list[list[str]]]:
    """For every UNIQUE constraint *and* unique index: the document paths of
    its columns. A partial index (``postgresql_where``) is checked as if it
    were total — a false positive there is a report to read, a miss would be
    a failed backfill."""
    paths = spine_paths(table)
    keys = []
    uniques = [c for c in table.constraints if type(c).__name__ == "UniqueConstraint"]
    uniques += [i for i in table.indexes if i.unique]
    for unique in uniques:
        cols = [c.name for c in getattr(unique, "columns", [])]
        if cols and all(c in paths for c in cols):
            keys.append([paths[c] for c in cols])
    return keys


def id_range(table: Table, after: Optional[str], upto: str):
    """Rows of one Mongo batch: ids in ``(after, upto]`` (``after`` None: from the start)."""
    if after is None:
        return table.c.id <= upto
    return and_(table.c.id > after, table.c.id <= upto)


def adapt_batch(size: int, seconds: float) -> int:
    if seconds > SLOW_BATCH_S:
        return max(MIN_BATCH, size // 2)
    if seconds < FAST_BATCH_S:
        return min(MAX_BATCH, size * 2)
    return size


class Runner:
    def __init__(self, target: Target):
        self.target = target
        self.run_id = uuid.uuid4().hex[:12]
        self._engine: Optional[AsyncEngine] = None
        self._mongo: Optional[AsyncMongoClient] = None

    # -- lifecycle ----------------------------------------------------------
    async def __aenter__(self) -> "Runner":
        settings = DatabaseSettings.from_env()
        settings = DatabaseSettings(
            url=self.target.database_url,
            pool_size=2,
            max_overflow=0,
            statement_timeout_ms=settings.statement_timeout_ms,
            lock_timeout_ms=settings.lock_timeout_ms,
            idle_in_transaction_ms=settings.idle_in_transaction_ms,
        )
        self._engine = make_engine(
            settings, application_name=self.target.application_name
        )
        self._mongo = AsyncMongoClient(
            self.target.mongo_uri, tz_aware=True, readPreference="secondaryPreferred"
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._engine is not None:
            await self._engine.dispose()
        if self._mongo is not None:
            await self._mongo.close()

    @property
    def engine(self) -> AsyncEngine:
        assert self._engine is not None
        return self._engine

    def collection(self, name: str):
        assert self._mongo is not None
        return self._mongo[self.target.mongo_db][name]

    def tables_for(self, collections: Optional[Iterable[str]]) -> dict[str, Table]:
        if not collections:
            return dict(self.target.tables)
        unknown = [c for c in collections if c not in self.target.tables]
        if unknown:
            raise SystemExit(f"unknown collection(s): {', '.join(unknown)}")
        return {c: self.target.tables[c] for c in collections}

    # -- progress -------------------------------------------------------------
    async def _progress_rows(self) -> dict[str, dict]:
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(self.target.progress))).mappings().all()
        return {r["collection"]: dict(r) for r in rows}

    async def _checkpoint(self, collection: str, **values: Any) -> None:
        now = datetime.now(timezone.utc)
        values = {
            **values,
            "collection": collection,
            "updated_at": now,
            "heartbeat_at": now,
            "run_id": self.run_id,
        }
        stmt = pg_insert(self.target.progress).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["collection"],
            set_={k: v for k, v in values.items() if k != "collection"},
        )
        async with self.engine.begin() as conn:
            await conn.execute(stmt)

    async def _refuse_if_running(
        self, collection: str, progress: dict[str, dict]
    ) -> None:
        row = progress.get(collection)
        if row and row["state"] == STATE_RUNNING and row.get("heartbeat_at"):
            age = (datetime.now(timezone.utc) - row["heartbeat_at"]).total_seconds()
            if age < STALLED_AFTER_S and row.get("run_id") != self.run_id:
                raise SystemExit(
                    f"{collection}: another run ({row['run_id']}) heartbeated {int(age)}s ago; "
                    f"refusing to start. If it is dead, wait {STALLED_AFTER_S}s or run `status`."
                )

    async def _advisory_lock(self, conn) -> bool:
        key = f"bc_migrate:{self.target.schema}"
        return bool(
            (
                await conn.execute(
                    text("SELECT pg_try_advisory_lock(hashtext(:k))"), {"k": key}
                )
            ).scalar()
        )

    # -- preflight ------------------------------------------------------------
    async def preflight(
        self, collections: Optional[Iterable[str]] = None
    ) -> list[CollectionReport]:
        reports = []
        for name, table in self.tables_for(collections).items():
            report = CollectionReport(name)
            coll = self.collection(name)
            report.mongo = await coll.count_documents({})
            report.invalid_ids = await coll.count_documents(
                {"_id": {"$not": {"$type": "objectId"}}}
            )
            for key in unique_key_paths(table):
                group = {"_".join(p): "$" + ".".join(p) for p in key}
                present = {".".join(p): {"$nin": [None, ""]} for p in key}
                pipeline = [
                    {"$match": present},
                    {"$group": {"_id": group, "n": {"$sum": 1}}},
                    {"$match": {"n": {"$gt": 1}}},
                    {"$count": "groups"},
                ]
                dupes = await (await coll.aggregate(pipeline)).to_list()
                report.duplicates += dupes[0]["groups"] if dupes else 0
            async with self.engine.connect() as conn:
                report.postgres = (
                    await conn.execute(select(func.count()).select_from(table))
                ).scalar_one()
            reports.append(report)
            logger.info(
                "preflight %s: mongo=%d postgres=%d invalid_ids=%d duplicate_keys=%d",
                name,
                report.mongo,
                report.postgres,
                report.invalid_ids,
                report.duplicates,
            )
        return reports

    # -- backfill ---------------------------------------------------------------
    async def backfill(
        self,
        collections: Optional[Iterable[str]] = None,
        *,
        dry_run: bool = False,
        max_minutes: Optional[float] = None,
        max_batches: Optional[int] = None,
        restart: bool = False,
        batch_size: int = 200,
    ) -> dict[str, dict]:
        deadline = time.monotonic() + max_minutes * 60 if max_minutes else None
        progress = await self._progress_rows()
        results: dict[str, dict] = {}
        async with self.engine.connect() as lock_conn:
            if not dry_run and not await self._advisory_lock(lock_conn):
                raise SystemExit(
                    "another migration run holds the advisory lock for this schema"
                )
            for name, table in self.tables_for(collections).items():
                await self._refuse_if_running(name, progress)
                state = progress.get(name) or {}
                if restart or not state:
                    last_id, copied, skipped, size = None, 0, 0, batch_size
                else:
                    if state["state"] == STATE_DONE and not restart:
                        results[name] = {
                            "state": STATE_DONE,
                            "count": state["count"],
                            "note": "already done",
                        }
                        continue
                    last_id, copied, skipped, size = (
                        state["last_id"],
                        state["count"],
                        state["skipped"],
                        state["batch_size"],
                    )
                try:
                    results[name] = await self._backfill_collection(
                        name,
                        table,
                        last_id,
                        copied,
                        skipped,
                        size,
                        dry_run=dry_run,
                        deadline=deadline,
                        max_batches=max_batches,
                    )
                except Exception as exc:  # noqa: BLE001 — recorded; the run goes on
                    logger.error(
                        "backfill %s failed: %s: %s",
                        name,
                        type(exc).__name__,
                        str(exc)[:300],
                    )
                    results[name] = {
                        "state": STATE_ERROR,
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }
                    continue
                if (
                    results[name]["state"] == STATE_PAUSED
                    and deadline
                    and time.monotonic() >= deadline
                ):
                    logger.info("time budget reached; stopping at a checkpoint")
                    break
        return results

    async def _backfill_collection(
        self,
        name,
        table,
        last_id,
        copied,
        skipped,
        size,
        *,
        dry_run,
        deadline,
        max_batches,
    ) -> dict:
        coll = self.collection(name)
        batches = 0
        if not dry_run:
            await self._checkpoint(
                name,
                state=STATE_RUNNING,
                last_id=last_id,
                count=copied,
                skipped=skipped,
                batch_size=size,
            )
        try:
            while True:
                if deadline and time.monotonic() >= deadline:
                    state = STATE_PAUSED
                    break
                if max_batches is not None and batches >= max_batches:
                    state = STATE_PAUSED
                    break
                query = {"_id": {"$gt": ObjectId(last_id)}} if last_id else {}
                started = time.monotonic()
                documents = await coll.find(query).sort("_id", 1).limit(size).to_list()
                if not documents:
                    state = STATE_DONE
                    break
                rows, bad = [], 0
                for document in documents:
                    if not is_object_id(document.get("_id")):
                        bad += 1
                        continue
                    rows.append(row_from_document(document))
                if rows and not dry_run:
                    stmt = pg_insert(table).values(rows)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "doc": stmt.excluded.doc,
                            "created_at": stmt.excluded.created_at,
                            "updated_at": stmt.excluded.updated_at,
                            "_bc_checksum": stmt.excluded._bc_checksum,
                        },
                        where=table.c._bc_source == SOURCE_BACKFILL,  # never an app row
                    )
                    async with self.engine.begin() as conn:
                        await conn.execute(stmt)
                # only ObjectId _ids can be checkpointed (the sort is by _id)
                object_ids = [
                    d["_id"] for d in documents if isinstance(d["_id"], ObjectId)
                ]
                if not object_ids:
                    state = STATE_DONE
                    break
                last_id = str(max(object_ids))
                copied += len(rows)
                skipped += bad
                elapsed = time.monotonic() - started
                batches += 1
                if not dry_run:
                    await self._checkpoint(
                        name,
                        state=STATE_RUNNING,
                        last_id=last_id,
                        count=copied,
                        skipped=skipped,
                        batch_size=size,
                    )
                logger.info(
                    "backfill %s: batch=%d rows=%d skipped=%d copied=%d last_id=%s %.0f rows/s",
                    name,
                    batches,
                    len(rows),
                    bad,
                    copied,
                    last_id,
                    len(rows) / max(elapsed, 1e-3),
                )
                size = adapt_batch(size, elapsed)
                if len(documents) < size and len(documents) < MIN_BATCH:
                    state = STATE_DONE
                    break
        except (
            Exception
        ) as exc:  # noqa: BLE001 — record, then re-raise: the checkpoint survives
            if not dry_run:
                await self._checkpoint(
                    name,
                    state=STATE_ERROR,
                    last_id=last_id,
                    count=copied,
                    skipped=skipped,
                    batch_size=size,
                    note=f"{type(exc).__name__}: {str(exc)[:200]}",
                )
            raise
        if not dry_run:
            await self._checkpoint(
                name,
                state=state,
                last_id=last_id,
                count=copied,
                skipped=skipped,
                batch_size=size,
                note=None,
            )
        return {
            "state": state,
            "count": copied,
            "skipped": skipped,
            "last_id": last_id,
            "batches": batches,
        }

    # -- verify -------------------------------------------------------------
    async def verify(
        self,
        collections: Optional[Iterable[str]] = None,
        *,
        sample_every: int = 1,
        deep_per_batch: int = 5,
    ) -> list[CollectionReport]:
        """Tier 1 counts; tier 2 checksum merge-join over ids in batches; tier 3 a
        round-trip deep compare of the first ``deep_per_batch`` rows of each
        batch. ``sample_every=k`` checks every k-th batch (large collections)."""
        reports = []
        for name, table in self.tables_for(collections).items():
            report = CollectionReport(name)
            coll = self.collection(name)
            report.mongo = await coll.count_documents({})
            async with self.engine.connect() as conn:
                report.postgres = (
                    await conn.execute(select(func.count()).select_from(table))
                ).scalar_one()
            last_id, batch_no, size = None, 0, 500
            seen_pg_ids: set[str] = set()
            while True:
                query = {"_id": {"$gt": ObjectId(last_id)}} if last_id else {}
                documents = await coll.find(query).sort("_id", 1).limit(size).to_list()
                if not documents:
                    break
                batch_no += 1
                ids = [
                    str(d["_id"]) for d in documents if isinstance(d["_id"], ObjectId)
                ]
                if not ids:
                    break
                # the batch owns every id after the previous batch's last one, so a
                # Postgres row between two Mongo batches (or before the first) is seen
                lower, last_id = last_id, ids[-1]
                if (batch_no - 1) % sample_every:
                    continue
                mongo_side = {
                    str(d["_id"]): d
                    for d in documents
                    if isinstance(d["_id"], ObjectId)
                }
                async with self.engine.connect() as conn:
                    rows = (
                        await conn.execute(
                            select(table.c.id, table.c._bc_checksum, table.c.doc).where(
                                id_range(table, lower, last_id)
                            )
                        )
                    ).all()
                pg_side = {r[0]: (r[1], r[2]) for r in rows}
                for oid, document in mongo_side.items():
                    if oid not in pg_side:
                        report.missing_in_postgres += 1
                        report.samples["missing_in_postgres"][:5] = report.samples[
                            "missing_in_postgres"
                        ][:4] + [oid]
                        continue
                    if pg_side[oid][0] != checksum(canonical_document(document)):
                        report.mismatched += 1
                        if len(report.samples["mismatched"]) < 5:
                            report.samples["mismatched"].append(oid)
                for oid in pg_side:
                    if oid not in mongo_side:
                        report.missing_in_mongo += 1
                        if len(report.samples["missing_in_mongo"]) < 5:
                            report.samples["missing_in_mongo"].append(oid)
                for oid in list(mongo_side)[:deep_per_batch]:  # tier 3
                    if (
                        oid in pg_side
                        and from_canonical_document(pg_side[oid][1]) != mongo_side[oid]
                    ):
                        report.drifted += 1
                        if len(report.samples["drifted"]) < 5:
                            report.samples["drifted"].append(oid)
            # Postgres rows beyond Mongo's id range (ids sort the same in both)
            async with self.engine.connect() as conn:
                extra = select(func.count()).select_from(table)
                if last_id:
                    extra = extra.where(table.c.id > last_id)
                if sample_every == 1:
                    report.missing_in_mongo += (await conn.execute(extra)).scalar_one()
            # deleted records still present, in either store (never sampled)
            for row_id, _ in await self._deletion_victims(name, table):
                report.tombstoned += 1
                if len(report.samples["tombstoned"]) < 5:
                    report.samples["tombstoned"].append(row_id)
            reports.append(report)
            logger.info(
                "verify %s: mongo=%d postgres=%d missing_in_postgres=%d missing_in_mongo=%d mismatched=%d drifted=%d tombstoned=%d",
                name,
                report.mongo,
                report.postgres,
                report.missing_in_postgres,
                report.missing_in_mongo,
                report.mismatched,
                report.drifted,
                report.tombstoned,
            )
        return reports

    # -- reconcile ----------------------------------------------------------
    async def reconcile(
        self,
        collections: Optional[Iterable[str]] = None,
        *,
        direction: str = "mongo->postgres",
        dry_run: bool = False,
    ) -> dict[str, dict]:
        """Fix what ``verify`` finds. ``mongo->postgres`` (Phase 1, Mongo is
        authoritative): copy missing/mismatched documents, overwriting even
        ``app`` rows when the Mongo document is at least as new.
        ``postgres->mongo``: replace Mongo documents from rows (R2/R3 fallback).

        Deletes are honoured in both directions through the deletion
        tombstones (:mod:`common.db.tombstones`), before anything is copied:
        a deleted record whose copy survives on one side only (its mirror
        delete failed) has that copy deleted; one whose copies survive on
        both sides is reported (``tombstoned``) and left for an operator; and
        a deleted record is never copied in either direction. Any other row
        present on one side only is copied to the side the direction targets.
        Postgres tombstones past their retention are pruned at the end of a
        run (Mongo expires its own). The outboxes are drained only when
        every collection was reconciled (no ``--group``/``--collections``
        subset): their entries name a repository, not a collection."""
        selected = self.tables_for(collections)
        results = {}
        for name, table in selected.items():
            report = (await self.verify([name]))[0]
            fixed, deleted, kept = 0, 0, 0
            # samples are capped; walk the collection for the full set when anything differs
            if not report.clean:
                deleted, kept, victims = await self._honour_tombstones(
                    name, table, dry_run
                )
                fixed = await self._reconcile_collection(
                    name, table, direction, dry_run, never_copy=victims
                )
            results[name] = {
                "fixed": fixed,
                "deleted": deleted,
                "tombstoned": kept,
                "before": report.as_dict(),
                "direction": direction,
            }
        if not dry_run:
            await self._prune_tombstones()
        if set(selected) == set(self.target.tables):
            await self._drain_outbox(direction, dry_run)
        else:
            logger.info(
                "outbox not drained: only part of the collections was reconciled; "
                "run reconcile without --group/--collections to drain it"
            )
        return results

    # -- deletion tombstones ----------------------------------------------------
    async def _tombstones(self, name: str) -> dict:
        """id -> latest deleted_at for ``name``, from both stores' tombstones."""
        pg = tombstones.postgres_table(self.target.schema)
        async with self.engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(pg.c.row_id, pg.c.deleted_at).where(pg.c.collection == name)
                )
            ).all()
        found = await (
            self.collection(tombstones.COLLECTION)
            .find({"collection": name}, {"row_id": 1, "deleted_at": 1})
            .to_list()
        )
        return tombstones.merge(
            {r[0]: r[1] for r in rows}, {d["row_id"]: d["deleted_at"] for d in found}
        )

    async def _copies(self, name: str, table: Table, ids: list[str]):
        """(id -> Postgres updated_at, id -> Mongo updated_at) of the copies present."""
        async with self.engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(table.c.id, table.c.updated_at).where(table.c.id.in_(ids))
                )
            ).all()
        documents = await (
            self.collection(name)
            .find(
                {"_id": {"$in": [ObjectId(i) for i in ids if is_object_id(i)]}},
                {"updated_at": 1},
            )
            .to_list()
        )
        return {r[0]: r[1] for r in rows}, {
            str(d["_id"]): d.get("updated_at") for d in documents
        }

    async def _deletion_victims(self, name: str, table: Table) -> list:
        """``(id, (Postgres updated_at, Mongo updated_at, deleted_at))`` of
        every deleted record with a copy still present that was last written
        before the delete; a store without a copy gives ``MISSING``."""
        tomb = await self._tombstones(name)
        victims = []
        ids = sorted(tomb)
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            pg, mongo = await self._copies(name, table, chunk)
            for row_id in chunk:
                at = tomb[row_id]
                p = pg[row_id] if row_id in pg else MISSING
                m = mongo[row_id] if row_id in mongo else MISSING
                if (p is not MISSING and tombstones.is_victim(at, p)) or (
                    m is not MISSING and tombstones.is_victim(at, m)
                ):
                    victims.append((row_id, (p, m, at)))
        return victims

    async def _honour_tombstones(
        self, name: str, table: Table, dry_run: bool
    ) -> tuple[int, int, set]:
        """Delete the surviving copy of each deleted record present on one
        side only; report those present on both. Returns (deleted, reported,
        ids that must not be copied). A copy is deleted only while it is the
        one read (same ``updated_at``), never one written again since."""
        coll = self.collection(name)
        deleted, reported, never_copy = 0, 0, set()
        for row_id, (p, m, at) in await self._deletion_victims(name, table):
            never_copy.add(row_id)
            p_victim = p is not MISSING and tombstones.is_victim(at, p)
            m_victim = m is not MISSING and tombstones.is_victim(at, m)
            if p_victim and m is MISSING:
                if dry_run:
                    deleted += 1
                    continue
                async with self.engine.begin() as conn:
                    result = await conn.execute(
                        table.delete().where(
                            table.c.id == row_id,
                            table.c.updated_at.is_not_distinct_from(p),
                        )
                    )
                deleted += result.rowcount or 0
            elif m_victim and p is MISSING:
                if dry_run:
                    deleted += 1
                    continue
                result = await coll.delete_one(
                    {"_id": ObjectId(row_id), "updated_at": m}
                )
                deleted += result.deleted_count
            elif p_victim and m_victim:
                reported += 1
        if deleted or reported:
            logger.info(
                "reconcile %s: copies of deleted records deleted=%d present on both sides=%d",
                name,
                deleted,
                reported,
            )
        return deleted, reported, never_copy

    async def _prune_tombstones(self) -> None:
        """Drop Postgres tombstones past the retention (Mongo's expire by TTL)."""
        pg = tombstones.postgres_table(self.target.schema)
        before = datetime.now(timezone.utc) - timedelta(days=tombstones.RETENTION_DAYS)
        async with self.engine.begin() as conn:
            result = await conn.execute(pg.delete().where(pg.c.deleted_at < before))
        if result.rowcount:
            logger.info("tombstones pruned: %d", result.rowcount)

    async def _reconcile_collection(
        self, name, table, direction, dry_run, never_copy=frozenset()
    ) -> int:
        coll = self.collection(name)
        fixed, last_id, size = 0, None, 500
        while True:
            query = {"_id": {"$gt": ObjectId(last_id)}} if last_id else {}
            documents = await coll.find(query).sort("_id", 1).limit(size).to_list()
            documents = [d for d in documents if isinstance(d["_id"], ObjectId)]
            if not documents:
                break
            lower, last_id = last_id, str(documents[-1]["_id"])
            async with self.engine.connect() as conn:
                rows = (
                    await conn.execute(
                        select(
                            table.c.id,
                            table.c._bc_checksum,
                            table.c.updated_at,
                            table.c.doc,
                            table.c._bc_source,
                        ).where(id_range(table, lower, last_id))
                    )
                ).all()
            pg = {r[0]: r for r in rows}
            if direction == "mongo->postgres":
                to_write = []
                for document in documents:
                    oid = str(document["_id"])
                    if oid in never_copy:
                        continue  # a deleted record (tombstone): never copied
                    row = row_from_document(document)
                    current = pg.get(oid)
                    if current is None or current[1] != row["_bc_checksum"]:
                        mongo_updated = timestamp_of(document.get("updated_at"))
                        if (
                            current is not None
                            and current[4] == SOURCE_APP
                            and current[2]
                            and mongo_updated
                            and mongo_updated < current[2]
                        ):
                            continue  # the application wrote this row after Mongo's copy: keep it
                        to_write.append(row)
                if to_write and not dry_run:
                    stmt = pg_insert(table).values(to_write)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "doc": stmt.excluded.doc,
                            "created_at": stmt.excluded.created_at,
                            "updated_at": stmt.excluded.updated_at,
                            "_bc_checksum": stmt.excluded._bc_checksum,
                            "_bc_source": stmt.excluded._bc_source,
                        },
                    )
                    async with self.engine.begin() as conn:
                        await conn.execute(stmt)
                fixed += len(to_write)
                # rows Mongo does not have: those of deleted records were
                # handled by _honour_tombstones, verify reports the others
            else:  # postgres->mongo
                for oid, r in pg.items():
                    if oid in never_copy:
                        continue  # a deleted record (tombstone): never copied
                    document = from_canonical_document(r[3])
                    mongo_doc = next(
                        (d for d in documents if str(d["_id"]) == oid), None
                    )
                    if (
                        mongo_doc is None
                        or checksum(canonical_document(mongo_doc)) != r[1]
                    ):
                        if not dry_run:
                            await coll.replace_one(
                                {"_id": document["_id"]}, document, upsert=True
                            )
                        fixed += 1
        if direction == "postgres->mongo":  # rows beyond Mongo's range
            async with self.engine.connect() as conn:
                extra = select(table.c.id, table.c.doc)
                if last_id:
                    extra = extra.where(table.c.id > last_id)
                for row_id, doc in (await conn.execute(extra)).all():
                    if row_id in never_copy:
                        continue
                    document = from_canonical_document(doc)
                    if not dry_run:
                        await coll.replace_one(
                            {"_id": document["_id"]}, document, upsert=True
                        )
                    fixed += 1
        logger.info("reconcile %s (%s): fixed=%d", name, direction, fixed)
        return fixed

    async def _drain_outbox(self, direction: str, dry_run: bool) -> None:
        """Mirror-write failures name a repository and ids; after a full pass
        the affected rows agree, so mark them resolved (both stores)."""
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as conn:
            table = f'"{self.target.schema}"."mirror_write_failures"'
            exists = (
                await conn.execute(text(f"SELECT to_regclass('{table}')"))
            ).scalar()
            if exists is not None and not dry_run:
                result = await conn.execute(
                    text(
                        f"UPDATE {table} SET resolved_at = :now WHERE resolved_at IS NULL"
                    ),
                    {"now": now},
                )
                logger.info("outbox (postgres): resolved %d", result.rowcount)
        if not dry_run:
            result = await self.collection("mirror_write_failures").update_many(
                {"resolved_at": None}, {"$set": {"resolved_at": now}}
            )
            logger.info("outbox (mongo): resolved %d", result.modified_count)

    # -- status -------------------------------------------------------------
    async def status(self) -> dict:
        progress = await self._progress_rows()
        now = datetime.now(timezone.utc)
        for row in progress.values():
            hb = row.get("heartbeat_at")
            row["stalled"] = bool(
                row["state"] == STATE_RUNNING
                and hb
                and (now - hb).total_seconds() > STALLED_AFTER_S
            )
            for k in ("heartbeat_at", "updated_at"):
                if row.get(k):
                    row[k] = row[k].isoformat()
        outbox = {
            "mongo": await self.collection("mirror_write_failures").count_documents(
                {"resolved_at": None}
            )
        }
        async with self.engine.connect() as conn:
            table = f'"{self.target.schema}"."mirror_write_failures"'
            exists = (
                await conn.execute(text(f"SELECT to_regclass('{table}')"))
            ).scalar()
            outbox["postgres"] = (
                (
                    await conn.execute(
                        text(f"SELECT count(*) FROM {table} WHERE resolved_at IS NULL")
                    )
                ).scalar()
                if exists
                else None
            )
        return {
            "run_id": self.run_id,
            "schema": self.target.schema,
            "collections": progress,
            "outbox": outbox,
        }

    # -- the "migration verified" marker (common.db.marker) ---------------------
    @staticmethod
    def _backfill_running(row: Optional[dict], now: datetime) -> bool:
        if not row or row.get("state") != STATE_RUNNING:
            return False
        heartbeat = row.get("heartbeat_at")
        return bool(heartbeat and (now - heartbeat).total_seconds() < STALLED_AFTER_S)

    def _marker_values(
        self,
        scope: str,
        groups: list[str],
        collections: dict,
        verified_at: datetime,
        based_on: Optional[list] = None,
    ) -> dict:
        return {
            "service": self.target.service,
            "scope": scope,
            "groups": groups,
            "collections": collections,
            "verified_at": verified_at,
            "code_version": self.target.code_version,
            "run_id": self.run_id,
            "based_on": based_on,
        }

    async def record_verify(
        self,
        reports: list[CollectionReport],
        *,
        sample_every: int = 1,
        subset: bool = False,
    ) -> dict:
        """Record what a ``verify`` run proved (see :mod:`common.db.marker`):
        a ``group`` row per repository group whose collections were all
        verified clean with equal counts, and the service marker when every
        group was, in this run or by combining the latest group rows.
        ``subset``: the run was limited by ``--collections`` (never recorded)."""
        outcome: dict[str, Any] = {"groups": [], "marker": None, "reason": None}
        marker = self.target.marker
        if marker is None:
            outcome["reason"] = "this service has no marker table"
            return outcome
        if sample_every != 1:
            outcome["reason"] = "a sampled verify (--sample-every > 1) is not recorded"
            return outcome
        if subset:
            outcome["reason"] = "a --collections verify is not recorded; use --group"
            return outcome
        by_name = {r.collection: r for r in reports}
        progress = await self._progress_rows()
        now = datetime.now(timezone.utc)
        busy = sorted(
            c for c in by_name if self._backfill_running(progress.get(c), now)
        )
        if busy:
            outcome["reason"] = f"a backfill is running for: {', '.join(busy)}"
            return outcome

        def counts(name: str) -> dict:
            report = by_name[name]
            return {
                "group": self.target.group_of(name),
                "mongo": report.mongo,
                "postgres": report.postgres,
            }

        def verified(name: str) -> bool:
            report = by_name.get(name)
            return bool(report and report.clean and report.mongo == report.postgres)

        all_groups = self.target.group_names()
        clean_groups = [
            g
            for g in all_groups
            if all(verified(n) for n in self.target.collections_of(g))
        ]
        values = [
            self._marker_values(
                SCOPE_GROUP,
                [group],
                {n: counts(n) for n in self.target.collections_of(group)},
                now,
            )
            for group in clean_groups
        ]
        full = clean_groups == all_groups
        if full:
            values.append(
                self._marker_values(
                    SCOPE_SERVICE,
                    all_groups,
                    {n: counts(n) for n in self.target.tables},
                    now,
                )
            )
        if values:
            async with self.engine.begin() as conn:
                await conn.execute(marker.insert(), values)
        outcome["groups"] = clean_groups
        if full:
            outcome["marker"] = "written"
        elif not clean_groups:
            outcome["reason"] = "no group was verified clean in full"
        else:
            combined, reason = await self._combine_group_rows(now, progress)
            outcome["marker"] = "combined" if combined else None
            outcome["reason"] = reason
        logger.info(
            "verify recorded: groups=%s marker=%s%s",
            ",".join(clean_groups) or "-",
            outcome["marker"] or "none",
            f" ({outcome['reason']})" if outcome["reason"] else "",
        )
        return outcome

    async def _combine_group_rows(
        self, now: datetime, progress: dict[str, dict]
    ) -> tuple[bool, Optional[str]]:
        """Write the service marker from the latest clean row of every group,
        when each covers its group's current collections, is at most
        COMBINE_WINDOW old and was not followed by a backfill of them."""
        marker = self.target.marker
        assert marker is not None
        based_on: list[dict] = []
        collections: dict[str, dict] = {}
        oldest = now
        async with self.engine.begin() as conn:
            for group in self.target.group_names():
                row = (
                    (
                        await conn.execute(
                            select(marker)
                            .where(
                                marker.c.scope == SCOPE_GROUP,
                                marker.c.groups.contains([group]),
                            )
                            .order_by(marker.c.id.desc())
                            .limit(1)
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    return False, f"group {group} has no clean verify yet"
                names = self.target.collections_of(group)
                missing = [n for n in names if n not in (row["collections"] or {})]
                if missing:
                    return False, (
                        f"group {group}: its last clean verify does not cover "
                        f"{', '.join(missing)}"
                    )
                if row["verified_at"] < now - COMBINE_WINDOW:
                    return False, (
                        f"group {group}: its last clean verify is older than "
                        f"{COMBINE_WINDOW.days} days"
                    )
                touched = [
                    progress[n]["updated_at"]
                    for n in names
                    if progress.get(n) and progress[n].get("updated_at")
                ]
                if touched and max(touched) >= row["verified_at"]:
                    return (
                        False,
                        f"group {group} was backfilled after its last clean verify",
                    )
                based_on.append(
                    {
                        "group": group,
                        "run_id": row["run_id"],
                        "verified_at": row["verified_at"].isoformat(),
                    }
                )
                collections.update({n: row["collections"][n] for n in names})
                oldest = min(oldest, row["verified_at"])
            await conn.execute(
                marker.insert(),
                self._marker_values(
                    SCOPE_SERVICE,
                    self.target.group_names(),
                    collections,
                    oldest,
                    based_on,
                ),
            )
        return True, None

    async def _marker_table_exists(self, conn) -> bool:
        return (
            await conn.scalar(
                text("SELECT to_regclass(:t)"),
                {"t": f'"{self.target.schema}".{MARKER_TABLE}'},
            )
            is not None
        )

    async def _last_verifies(self) -> tuple[dict[str, Optional[dict]], Optional[dict]]:
        """(group -> its latest clean verify, the latest clean verify of any scope)."""
        marker = self.target.marker
        groups: dict[str, Optional[dict]] = {g: None for g in self.target.group_names()}
        if marker is None:
            return groups, None
        async with self.engine.connect() as conn:
            if not await self._marker_table_exists(conn):
                return groups, None
            rows = (
                (await conn.execute(select(marker).order_by(marker.c.id.desc())))
                .mappings()
                .all()
            )

        def brief(row) -> dict:
            return {
                "scope": row["scope"],
                "groups": row["groups"],
                "verified_at": row["verified_at"].isoformat(),
                "run_id": row["run_id"],
                "code_version": row["code_version"],
            }

        for row in rows:
            if row["scope"] != SCOPE_GROUP:
                continue
            for group in row["groups"]:
                if group in groups and groups[group] is None:
                    groups[group] = brief(row)
        return groups, (brief(rows[0]) if rows else None)

    async def _mirror_failures(self) -> dict:
        """Mirror-write failures per store: total, unresolved (the outbox
        depth) and the unresolved ones per repository method. Counts only."""
        coll = self.collection("mirror_write_failures")
        by_method = await (
            await coll.aggregate(
                [
                    {"$match": {"resolved_at": None}},
                    {
                        "$group": {
                            "_id": {"t": "$table_name", "op": "$op"},
                            "n": {"$sum": 1},
                        }
                    },
                ]
            )
        ).to_list()
        out: dict[str, Any] = {
            "mongo": {
                "total": await coll.count_documents({}),
                "unresolved": sum(d["n"] for d in by_method),
                "unresolved_by_method": {
                    f"{d['_id'].get('t')}.{d['_id'].get('op')}": d["n"]
                    for d in by_method
                },
            }
        }
        table = f'"{self.target.schema}"."mirror_write_failures"'
        async with self.engine.connect() as conn:
            exists = (
                await conn.execute(text(f"SELECT to_regclass('{table}')"))
            ).scalar()
            if exists is None:
                out["postgres"] = None
                return out
            total = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
            rows = (
                await conn.execute(
                    text(
                        f"SELECT table_name, op, count(*) FROM {table} "
                        "WHERE resolved_at IS NULL GROUP BY table_name, op"
                    )
                )
            ).all()
        out["postgres"] = {
            "total": total,
            "unresolved": sum(r[2] for r in rows),
            "unresolved_by_method": {f"{r[0]}.{r[1]}": r[2] for r in rows},
        }
        return out

    async def status_report(self, collections: Optional[Iterable[str]] = None) -> dict:
        """``status --json``: one machine-readable document for operators:
        counts per collection in both stores, backfill checkpoints, outbox
        depth, mirror failures, the last clean verify (per group and overall)
        and the marker. Names and counts only, never document contents."""
        tables = self.tables_for(collections)
        base = await self.status()
        per_collection: dict[str, dict] = {}
        for name, table in tables.items():
            async with self.engine.connect() as conn:
                postgres = (
                    await conn.execute(select(func.count()).select_from(table))
                ).scalar_one()
            per_collection[name] = {
                "group": self.target.group_of(name),
                "mongo": await self.collection(name).count_documents({}),
                "postgres": postgres,
                "backfill": base["collections"].get(name),
            }
        last_by_group, last = await self._last_verifies()
        selected = {self.target.group_of(n) for n in tables}
        async with self.engine.connect() as conn:
            marker: Optional[MarkerInfo] = await migration_verified(
                conn,
                self.target.service,
                schema=self.target.schema,
                collections=list(self.target.tables),
            )
        return {
            "format": 1,
            "service": self.target.service,
            "schema": self.target.schema,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "code_version": self.target.code_version,
            "collections": per_collection,
            "groups": {
                g: {
                    "collections": [
                        n for n in self.target.collections_of(g) if n in tables
                    ],
                    "last_verify": last_by_group.get(g),
                }
                for g in self.target.group_names()
                if g in selected
            },
            "outbox": base["outbox"],
            "mirror_failures": await self._mirror_failures(),
            "last_verify": last,
            "marker": marker.as_dict() if marker else None,
        }
