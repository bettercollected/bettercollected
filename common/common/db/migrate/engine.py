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
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from bson import ObjectId
from pymongo import AsyncMongoClient, ReadPreference
from pymongo.errors import DuplicateKeyError
from sqlalchemy import Table, and_, func, literal, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.elements import ColumnClause

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
# The outbox ``error`` of a copy whose re-check failed (common.db.convergence)
UNVERIFIED_ERROR = "CopyUnverified:"


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
    # repository groups served from Postgres only: their collections are
    # imported (preflight, backfill, status) but never verified or reconciled,
    # and the marker covers the other groups
    postgres_only_groups: tuple[str, ...] = ()
    # the service's effective flags from an environment (its own loader, e.g.
    # one that pins the Postgres-only groups); None: common.db.flags.load_flags
    load_flags: Optional[Callable[[Mapping[str, str]], Any]] = None

    def group_of(self, collection: str) -> str:
        return self.groups.get(collection) or self.service or self.schema

    def is_postgres_only(self, collection: str) -> bool:
        return self.group_of(collection) in self.postgres_only_groups

    def migrating_groups(self) -> list[str]:
        """:meth:`group_names` without the Postgres-only groups."""
        return [g for g in self.group_names() if g not in self.postgres_only_groups]

    def migrating_tables(self) -> dict[str, Table]:
        """The collections of :meth:`migrating_groups` and their tables."""
        return {c: t for c, t in self.tables.items() if not self.is_postgres_only(c)}

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
    # copies of a collection Mongo expires by TTL that have expired, either
    # store: absent, as for reconcile (never a difference, never "clean" on
    # their own account); ``mongo``/``postgres`` above still count them
    expired: int = 0
    invalid_ids: int = 0
    duplicates: int = 0
    # preflight, of the unique keys compared ignoring letter case
    # (lower(email)): distinct lower-cased values that more than one document
    # holds, and how many documents hold them. Counted in ``duplicates`` too.
    case_variant_keys: int = 0
    case_variant_documents: int = 0
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
    # an index over expressions (lower(email)) is checked by
    # casefold_unique_key_paths; its columns alone are not its key
    uniques += [
        i
        for i in table.indexes
        if i.unique and all(isinstance(e, ColumnClause) for e in i.expressions)
    ]
    for unique in uniques:
        cols = [c.name for c in getattr(unique, "columns", [])]
        if cols and all(c in paths for c in cols):
            keys.append([paths[c] for c in cols])
    return keys


def casefold_unique_key_paths(table: Table) -> list[list[str]]:
    """The document path of every unique index over ``lower(<column>)``
    (e.g. emails unique ignoring case): preflight groups those keys
    lower-cased, as Postgres will compare them."""
    paths = spine_paths(table)
    keys = []
    for index in table.indexes:
        if not index.unique or len(index.expressions) != 1:
            continue
        expression = index.expressions[0]
        if getattr(expression, "name", "").lower() != "lower":
            continue
        arguments = list(getattr(expression, "clauses", []))
        if len(arguments) == 1 and getattr(arguments[0], "name", None) in paths:
            keys.append(paths[arguments[0].name])
    return keys


def id_range(table: Table, after: Optional[str], upto: str):
    """Rows of one Mongo batch: ids in ``(after, upto]`` (``after`` None: from the start)."""
    if after is None:
        return table.c.id <= upto
    return and_(table.c.id > after, table.c.id <= upto)


def expired(document: Mapping[str, Any], ttl: Optional[tuple], now: datetime) -> bool:
    """Whether a copy of a collection Mongo expires by TTL has expired:
    verify and reconcile treat it as absent, like convergence does. Only a
    date counts, as for Mongo's TTL monitor: a string (an ISO timestamp)
    never expires there, so it is a live copy here too."""
    if ttl is None:
        return False
    field_name, seconds = ttl
    value = document.get(field_name)
    if not isinstance(value, datetime):
        return False
    at = timestamp_of(value)
    return at is not None and at + timedelta(seconds=seconds) <= now


async def case_variants(coll, path: Sequence[str]) -> tuple[int, int]:
    """(distinct lower-cased values more than one document holds, documents
    holding them) at ``path``: string values only, empty ones ignored."""
    field_path = ".".join(path)
    pipeline = [
        {"$match": {field_path: {"$type": "string", "$ne": ""}}},
        {"$group": {"_id": {"$toLower": "$" + field_path}, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
        {"$group": {"_id": None, "keys": {"$sum": 1}, "documents": {"$sum": "$n"}}},
    ]
    found = await (await coll.aggregate(pipeline)).to_list()
    return (found[0]["keys"], found[0]["documents"]) if found else (0, 0)


def on_primary(collection):
    """``collection`` read from the primary: the runner scans from a secondary,
    but a compare-and-set must compare with the current copy."""
    return collection.with_options(read_preference=ReadPreference.PRIMARY)


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
            for path in casefold_unique_key_paths(table):
                keys, documents = await case_variants(coll, path)
                report.case_variant_keys += keys
                report.case_variant_documents += documents
                report.duplicates += keys
            if report.case_variant_keys:
                # counts only: the values are personal data (email addresses)
                logger.warning(
                    "preflight %s: %d values are held by %d documents that differ "
                    "only in letter case; Postgres requires them unique ignoring "
                    "case, so backfill stops this collection on the first one: "
                    "resolve them before the import (docs/postgres-cutover-runbook.md, "
                    "'Accounts whose emails differ only in case')",
                    name,
                    report.case_variant_keys,
                    report.case_variant_documents,
                )
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
        # what a clean result can vouch for: only what existed when it started
        self._verify_started = now = datetime.now(timezone.utc)
        reports = []
        for name, table in self.tables_for(collections).items():
            report = CollectionReport(name)
            coll = self.collection(name)
            # a copy past its TTL is absent, in either store, as reconcile
            # treats it: Mongo's TTL monitor drops it on its own schedule
            ttl = await self._ttl_of(coll)
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
                if ttl is not None:
                    gone_mongo = [
                        oid for oid, d in mongo_side.items() if expired(d, ttl, now)
                    ]
                    gone_pg = [
                        oid
                        for oid, (_, doc) in pg_side.items()
                        if expired(from_canonical_document(doc), ttl, now)
                    ]
                    report.expired += len(gone_mongo) + len(gone_pg)
                    for oid in gone_mongo:
                        del mongo_side[oid]
                    for oid in gone_pg:
                        del pg_side[oid]
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
            if sample_every == 1:
                report.missing_in_mongo += await self._rows_beyond(
                    table, last_id, ttl, now, report
                )
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

    async def _rows_beyond(self, table, last_id, ttl, now, report) -> int:
        """How many Postgres rows have an id past Mongo's last one (all of
        them when Mongo has none); an expired copy is absent, so it is
        counted under ``report.expired`` instead."""
        if ttl is None:
            async with self.engine.connect() as conn:
                extra = select(func.count()).select_from(table)
                if last_id:
                    extra = extra.where(table.c.id > last_id)
                return (await conn.execute(extra)).scalar_one()
        live, after = 0, last_id
        while True:  # in id order, a batch at a time: never the whole table
            extra = select(table.c.id, table.c.doc).order_by(table.c.id).limit(500)
            if after:
                extra = extra.where(table.c.id > after)
            async with self.engine.connect() as conn:
                rows = (await conn.execute(extra)).all()
            if not rows:
                return live
            after = rows[-1][0]
            for row_id, doc in rows:
                if expired(from_canonical_document(doc), ttl, now):
                    report.expired += 1
                    continue
                live += 1
                if len(report.samples["missing_in_mongo"]) < 5:
                    report.samples["missing_in_mongo"].append(row_id)

    # -- reconcile ----------------------------------------------------------
    async def reconcile(
        self,
        collections: Optional[Iterable[str]] = None,
        *,
        direction: str = "mongo->postgres",
        dry_run: bool = False,
        mongo_primary: Iterable[str] = (),
    ) -> dict[str, dict]:
        """Fix what ``verify`` finds. ``mongo->postgres`` (Phase 1, Mongo is
        authoritative): copy missing/mismatched documents, overwriting even
        ``app`` rows when the Mongo document is at least as new — or, in a
        group named in ``mongo_primary`` (the services write Mongo first:
        ``mongo``/``dual``; the CLI's ``--mongo-wins``), whatever their age —
        unless the Postgres-side outbox holds unresolved entries (writes from
        a time Postgres was primary): then in no group. A row the application wrote
        after Mongo's copy in any other group (Postgres is the primary) is
        kept and counted as ``newer_in_postgres``: run ``postgres->mongo``
        for it. ``postgres->mongo``: replace Mongo documents from rows (R2/R3
        fallback).

        Under a Mongo primary a newer row in Postgres is a write Mongo does
        not hold: a mirror that applied two writes in the other order, or
        a Postgres copy restored from a later point than Mongo's. Mongo is
        what the services read, so its copy wins; a write racing reconcile
        is still left alone by the compare-and-set below (Mongo is written
        first, so the re-read of Mongo sees it).

        Each copy is a compare-and-set against what this run read: a row or
        document the application changed in the meantime (a write whose
        mirror landed while reconcile was between its read and its write) is
        left as the application wrote it and counted as ``skipped``; the
        next ``verify`` shows whether it still differs.

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
        subset; the Postgres-only groups' collections need not be, they
        mirror nothing): their entries name a repository, not a collection."""
        selected = self.tables_for(collections)
        mongo_primary = set(mongo_primary)
        if mongo_primary and direction == "mongo->postgres":
            pending = await self._open_postgres_outbox()
            if pending:
                # writes made while Postgres was primary whose Mongo mirror
                # failed (a rollback to dual since): their rows may be the
                # newer ones. The entries name a repository and best-effort
                # ids, not reliably the rows, so Mongo wins nowhere.
                logger.warning(
                    "reconcile: %d unresolved mirror failures were recorded while "
                    "Postgres was primary; Mongo's copy wins nowhere in this run "
                    "(newer Postgres rows are kept). Run reconcile --direction "
                    "postgres->mongo while Postgres is primary to copy them",
                    pending,
                )
                mongo_primary = set()
        results = {}
        for name, table in selected.items():
            report = (await self.verify([name]))[0]
            fixed, skipped, deleted, kept, newer = 0, 0, 0, 0, 0
            # samples are capped; walk the collection for the full set when anything differs
            if not report.clean:
                deleted, kept, victims = await self._honour_tombstones(
                    name, table, dry_run
                )
                fixed, skipped, newer = await self._reconcile_collection(
                    name,
                    table,
                    direction,
                    dry_run,
                    never_copy=victims,
                    mongo_wins=self.target.group_of(name) in mongo_primary,
                )
            results[name] = {
                "fixed": fixed,
                "skipped": skipped,
                "newer_in_postgres": newer,
                "deleted": deleted,
                "tombstoned": kept,
                "before": report.as_dict(),
                "direction": direction,
            }
        if not dry_run:
            await self._prune_tombstones()
        skipped_any = sum(r["skipped"] for r in results.values())
        newer_any = sum(r["newer_in_postgres"] for r in results.values())
        if skipped_any:
            logger.info(
                "outbox not drained: %d copies were skipped because the application "
                "changed them meanwhile; run verify, then reconcile again",
                skipped_any,
            )
        elif newer_any:
            logger.info(
                "outbox not drained: %d Postgres rows are newer than Mongo's copy "
                "and Postgres is their primary; reconcile --direction "
                "postgres->mongo copies them",
                newer_any,
            )
        elif set(selected) >= set(self.target.migrating_tables()):
            await self._drain_outbox(direction, dry_run)
        else:
            logger.info(
                "outbox not drained: only part of the collections was reconciled; "
                "run reconcile without --group/--collections to drain it"
            )
        return results

    # -- deletion tombstones ----------------------------------------------------
    async def _tombstones(self, name: str, ids: Optional[list] = None) -> dict:
        """id -> latest deleted_at for ``name`` (only ``ids``, when given),
        from both stores' tombstones; Mongo's read from its primary."""
        pg = tombstones.postgres_table(self.target.schema)
        query = select(pg.c.row_id, pg.c.deleted_at).where(pg.c.collection == name)
        mongo_query: dict = {"collection": name}
        if ids is not None:
            query = query.where(pg.c.row_id.in_(ids))
            mongo_query["row_id"] = {"$in": ids}
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        found = await (
            on_primary(self.collection(tombstones.COLLECTION))
            .find(mongo_query, {"row_id": 1, "deleted_at": 1})
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

    @staticmethod
    async def _ttl_of(coll) -> Optional[tuple[str, int]]:
        """(field, seconds) of the collection's TTL index in Mongo, or None."""
        try:
            indexes = await coll.index_information()
        except Exception:  # noqa: BLE001 — no collection yet: no TTL
            return None
        for spec in indexes.values():
            if "expireAfterSeconds" in spec and len(spec.get("key", [])) == 1:
                return spec["key"][0][0], int(spec["expireAfterSeconds"])
        return None

    async def _prune_tombstones(self) -> None:
        """Drop Postgres tombstones past the retention (Mongo's expire by TTL)."""
        pg = tombstones.postgres_table(self.target.schema)
        before = datetime.now(timezone.utc) - timedelta(days=tombstones.RETENTION_DAYS)
        async with self.engine.begin() as conn:
            result = await conn.execute(pg.delete().where(pg.c.deleted_at < before))
        if result.rowcount:
            logger.info("tombstones pruned: %d", result.rowcount)

    async def _reconcile_collection(
        self,
        name,
        table,
        direction,
        dry_run,
        never_copy=frozenset(),
        mongo_wins=False,
    ) -> tuple[int, int, int]:
        """(copies written, copies skipped because the target changed since
        it was read, application rows newer than Mongo's copy kept). Ids in
        ``never_copy`` (deleted records) are not copied. ``mongo_wins``: Mongo
        is the primary, its copy replaces a newer row too."""
        coll = self.collection(name)
        ttl = await self._ttl_of(coll)
        now = datetime.now(timezone.utc)
        fixed, skipped, newer, last_id, size = 0, 0, 0, None, 500
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
                    if expired(document, ttl, now):
                        continue  # Mongo's TTL drops it; the twin already may have
                    row = row_from_document(document)
                    current = pg.get(oid)
                    if current is None or current[1] != row["_bc_checksum"]:
                        mongo_updated = timestamp_of(document.get("updated_at"))
                        if (
                            not mongo_wins
                            and current is not None
                            and current[4] == SOURCE_APP
                            and current[2]
                            and mongo_updated
                            and mongo_updated < current[2]
                        ):
                            # the application wrote this row after Mongo's
                            # copy, and Postgres is its primary: keep it
                            newer += 1
                            continue
                        # the checksum read: the row is replaced only while it holds it
                        to_write.append((row, None if current is None else current[1]))
                if to_write and not dry_run:
                    # Mongo was read before Postgres: a document the application
                    # changed in between is not copied (its mirror write follows)
                    fresh = {
                        str(d["_id"]): checksum(canonical_document(d))
                        for d in await on_primary(coll)
                        .find(
                            {"_id": {"$in": [ObjectId(r["id"]) for r, _ in to_write]}}
                        )
                        .to_list()
                    }
                    unchanged = [
                        (r, expected)
                        for r, expected in to_write
                        if fresh.get(r["id"]) == r["_bc_checksum"]
                    ]
                    applied = await self._apply_to_postgres(table, unchanged)
                    fixed += applied
                    skipped += len(to_write) - applied
                elif to_write:
                    fixed += len(to_write)
                # rows Mongo does not have: those of deleted records were
                # handled by _honour_tombstones, verify reports the others
            else:  # postgres->mongo
                for oid, r in pg.items():
                    if oid in never_copy:
                        continue  # a deleted record (tombstone): never copied
                    document = from_canonical_document(r[3])
                    if expired(document, ttl, now):
                        continue  # expired: Mongo's TTL index would drop the copy
                    mongo_doc = next(
                        (d for d in documents if str(d["_id"]) == oid), None
                    )
                    if (
                        mongo_doc is None
                        or checksum(canonical_document(mongo_doc)) != r[1]
                    ):
                        if dry_run or await self._apply_to_mongo(
                            coll, table, document, mongo_doc, r[1]
                        ):
                            fixed += 1
                        else:
                            skipped += 1
        if direction == "postgres->mongo":  # rows beyond Mongo's range
            async with self.engine.connect() as conn:
                extra = select(table.c.id, table.c._bc_checksum, table.c.doc)
                if last_id:
                    extra = extra.where(table.c.id > last_id)
                for row_id, row_checksum, doc in (await conn.execute(extra)).all():
                    if row_id in never_copy:
                        continue
                    document = from_canonical_document(doc)
                    if expired(document, ttl, now):
                        continue
                    if dry_run or await self._apply_to_mongo(
                        coll, table, document, None, row_checksum
                    ):
                        fixed += 1
                    else:
                        skipped += 1
        logger.info(
            "reconcile %s (%s): fixed=%d skipped=%d newer_in_postgres=%d",
            name,
            direction,
            fixed,
            skipped,
            newer,
        )
        return fixed, skipped, newer

    async def _apply_to_postgres(
        self, table: Table, writes: list[tuple[dict, Optional[str]]]
    ) -> int:
        """Store each ``(row values, checksum read)``: a row that was absent
        is inserted only while it still is; a present one is updated (never
        inserted) only while it still holds the checksum read, so a row the
        application deleted meanwhile stays deleted. Returns how many were
        stored."""
        applied = 0
        name = next(c for c, t in self.target.tables.items() if t is table)
        pg_stones = tombstones.postgres_table(self.target.schema)
        async with self.engine.begin() as conn:
            for values, expected in writes:
                if expected is None:
                    # ... and only while no tombstone newer than the copy exists
                    # (a delete that landed after this run looked; the delete
                    # writes its tombstone in its own transaction)
                    columns = list(values)
                    deleted_since = (
                        select(literal(1))
                        .select_from(pg_stones)
                        .where(
                            pg_stones.c.collection == name,
                            pg_stones.c.row_id == values["id"],
                            func.date_trunc("milliseconds", pg_stones.c.deleted_at)
                            > func.date_trunc(
                                "milliseconds",
                                literal(values["updated_at"], table.c.updated_at.type),
                            ),
                        )
                        .exists()
                    )
                    source = select(
                        *[literal(values[c], table.c[c].type).label(c) for c in columns]
                    ).where(~deleted_since)
                    stmt = (
                        pg_insert(table)
                        .from_select(columns, source)
                        .on_conflict_do_nothing(index_elements=["id"])
                    )
                else:
                    stmt = (
                        table.update()
                        .where(
                            table.c.id == values["id"],
                            table.c._bc_checksum == expected,
                        )
                        .values(
                            {
                                name: values[name]
                                for name in (
                                    "doc",
                                    "created_at",
                                    "updated_at",
                                    "_bc_checksum",
                                    "_bc_source",
                                )
                            }
                        )
                    )
                applied += (await conn.execute(stmt)).rowcount or 0
        return applied

    async def _apply_to_mongo(
        self,
        coll,
        table: Table,
        document: dict,
        read: Optional[dict],
        row_checksum: str,
    ) -> bool:
        """Store ``document`` (the Postgres row read, with ``row_checksum``)
        in Mongo only while the row still holds that checksum (re-read here:
        a row the application deleted or changed meanwhile is not copied)
        and the Mongo copy is still the one read (``read``; ``None``: there
        was none). Returns whether it was stored."""
        if not await self._still_the_row(coll, table, document, row_checksum):
            return False
        if read is None:
            try:
                await self._insert_copy(coll, document)
            except DuplicateKeyError:
                return False
            # A delete that landed between the check above and the insert
            # (its tombstone, or the row gone) means the copy must go again.
            # A delete landing after this re-check removes the copy itself:
            # its Mongo delete (primary or mirror) runs after the row is gone.
            if await self._still_the_row(coll, table, document, row_checksum):
                return True
            removed = await coll.delete_one(
                {
                    "_id": document["_id"],
                    "$expr": {"$eq": ["$$ROOT", {"$literal": document}]},
                }
            )
            if not removed.deleted_count:
                # gone already (the application's own delete) or changed since:
                # either way not this run's copy any more; verify shows the rest
                logger.info(
                    "reconcile %s: the copy of %s inserted for a record deleted "
                    "meanwhile was no longer there to remove",
                    coll.name,
                    document["_id"],
                )
            return False
        result = await coll.replace_one(
            {
                "_id": document["_id"],
                "$expr": {"$eq": ["$$ROOT", {"$literal": read}]},
            },
            document,
        )
        return result.matched_count == 1

    async def _still_the_row(
        self, coll, table: Table, document: dict, row_checksum: str
    ) -> bool:
        """Whether the Postgres row still holds ``row_checksum`` and no store
        recorded its delete after the copy was written."""
        row_id = str(document["_id"])
        async with self.engine.connect() as conn:
            current = (
                await conn.execute(
                    select(table.c._bc_checksum).where(table.c.id == row_id)
                )
            ).scalar_one_or_none()
        if current != row_checksum:
            return False
        deleted_at = (await self._tombstones(coll.name, [row_id])).get(row_id)
        return not tombstones.is_victim(deleted_at, document.get("updated_at"))

    @staticmethod
    async def _insert_copy(coll, document: dict) -> None:
        await coll.insert_one(document)

    async def _drain_outbox(self, direction: str, dry_run: bool) -> None:
        """Mirror-write failures name a repository and ids; after a full pass
        the affected rows agree, so mark them resolved (both stores). Except
        an unverified copy (``CopyUnverified``): only a clean full ``verify``
        resolves those (:meth:`_resolve_unverified`)."""
        if not dry_run:
            await self._resolve_outbox(only_unverified=False)

    async def _open_postgres_outbox(self) -> int:
        """Unresolved entries of the Postgres-side outbox: mirror writes to
        Mongo that failed while Postgres was the primary."""
        table = f'"{self.target.schema}"."mirror_write_failures"'
        async with self.engine.connect() as conn:
            if (
                await conn.execute(text(f"SELECT to_regclass('{table}')"))
            ).scalar() is None:
                return 0
            return (
                await conn.execute(
                    text(f"SELECT count(*) FROM {table} WHERE resolved_at IS NULL")
                )
            ).scalar_one()

    async def _resolve_unverified(self) -> None:
        """A clean full verify: the stores agree, unverified copies included,
        but only those recorded before that verify started (one recorded
        while it ran may concern a copy it read before the copy landed)."""
        started = getattr(self, "_verify_started", None)
        if started is None:
            logger.info("unverified copies not resolved: no verify ran in this run")
            return
        await self._resolve_outbox(only_unverified=True, before=started)

    async def _resolve_outbox(
        self, *, only_unverified: bool, before: Optional[datetime] = None
    ) -> None:
        now = datetime.now(timezone.utc)
        unverified = UNVERIFIED_ERROR + "%"
        created = "" if before is None else " AND created_at < :before"
        async with self.engine.begin() as conn:
            table = f'"{self.target.schema}"."mirror_write_failures"'
            exists = (
                await conn.execute(text(f"SELECT to_regclass('{table}')"))
            ).scalar()
            if exists is not None:
                which = "LIKE" if only_unverified else "NOT LIKE"
                result = await conn.execute(
                    text(
                        f"UPDATE {table} SET resolved_at = :now "
                        f"WHERE resolved_at IS NULL AND error {which} :unverified"
                        f"{created}"
                    ),
                    {"now": now, "unverified": unverified, "before": before},
                )
                logger.info("outbox (postgres): resolved %d", result.rowcount)
        pattern = {"$regex": "^" + UNVERIFIED_ERROR}
        selector = {
            "resolved_at": None,
            "error": pattern if only_unverified else {"$not": pattern},
        }
        if before is not None:
            selector["created_at"] = {"$lt": before}
        result = await self.collection("mirror_write_failures").update_many(
            selector, {"$set": {"resolved_at": now}}
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
        group was, in this run or by combining the latest group rows (every
        group but the Postgres-only ones, which are never verified).
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

        all_groups = self.target.migrating_groups()
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
                    {n: counts(n) for n in self.target.migrating_tables()},
                    now,
                )
            )
        if values:
            async with self.engine.begin() as conn:
                await conn.execute(marker.insert(), values)
        outcome["groups"] = clean_groups
        if full:
            outcome["marker"] = "written"
            await self._resolve_unverified()
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
            for group in self.target.migrating_groups():
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
                    self.target.migrating_groups(),
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
                collections=list(self.target.migrating_tables()),
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
