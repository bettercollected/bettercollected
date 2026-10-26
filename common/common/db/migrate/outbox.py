"""Resolve Postgres-side outbox entries whose write Mongo provably holds.

An entry of ``<schema>.mirror_write_failures`` records a write made while
Postgres was a group's primary whose Mongo mirror failed. Until it is
resolved, ``reconcile`` (``mongo->postgres``) keeps every row the application
wrote, since any of them may be the only copy of that write. After a group is
rolled back to ``dual`` (Mongo first), a Mongo write whose Postgres mirror
failed then leaves an older application row behind that no reconcile
replaces, so ``verify`` is never clean and the entries never resolve (the
runbook's "stuck case"). ``resolve-outbox`` breaks that loop without losing a
write: by default it resolves an entry only on proof that Mongo holds what
Postgres holds, never on timestamps.

For each open entry (read once; entries recorded later are never touched):

* its group, from the repository the entry names (the routed repository's
  class name). An unknown repository keeps the entry.
* the rows it names: ``row_id`` is a best-effort list of the write's
  arguments (``common.db.runtime.failure_ids``), so each ObjectId among them
  is looked up in every collection of the group, in both stores.
* every row of the group, in both stores: the entry's write may have touched
  rows it does not name (a write by a foreign key, more ids than are
  recorded, a delete), so a single row of the group that is not proven keeps
  all the group's entries (``group_differs``).

A row is proven when (:func:`mongo_holds`):

* both copies have the same checksum;
* the Postgres row was copied from Mongo (``_bc_source = 'backfill'``): it
  holds no Postgres write;
* neither store holds a live copy (absent, or past Mongo's TTL, on both
  sides);
* Postgres's row was deleted after it was written (a newer tombstone, either
  store) and Mongo has no copy.

Anything else keeps the entry: ``missing_in_mongo``, ``missing_in_postgres``
(a Mongo copy Postgres lacks with no tombstone), ``delete_pending`` (a Mongo
copy older than a delete: ``reconcile`` removes it), ``expired_one_side``,
``older_in_mongo``, and ``superseded``: Mongo's copy differs and carries a
later ``updated_at``. A later stamp is no proof that Mongo got the write (a
save built from a copy that never had it stamps a later time too), so a
superseded entry is resolved only with ``accept_superseded`` (the CLI's
``--accept-superseded``), once the operator has confirmed that Mongo's newer
version should win: ``reconcile`` then discards those Postgres changes. Even
then Mongo's copy must be later than the Postgres row and not older than the
entry.

The result holds counts only. Entry ids, row ids and reasons go to a file
only when the operator names one (``--ids-file``), never to the output or
the logs: some row ids are derived from personal data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from bson import ObjectId
from sqlalchemy import Table, select, text

from common.db import tombstones
from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum, from_canonical_document
from common.db.migrate.engine import (
    OBJECT_ID,
    Runner,
    expired,
    on_primary,
    timestamp_of,
)

BATCH = 500
#: differing row ids kept for the ids file, per collection (the counts are not capped)
MAX_LISTED = 1000

MISSING_IN_MONGO = "missing_in_mongo"
MISSING_IN_POSTGRES = "missing_in_postgres"
OLDER_IN_MONGO = "older_in_mongo"
SUPERSEDED = "superseded"
DELETE_PENDING = "delete_pending"
EXPIRED_ONE_SIDE = "expired_one_side"
GROUP_DIFFERS = "group_differs"
UNKNOWN_REPOSITORY = "unknown_repository"
REASONS = (
    UNKNOWN_REPOSITORY,
    MISSING_IN_MONGO,
    MISSING_IN_POSTGRES,
    OLDER_IN_MONGO,
    SUPERSEDED,
    DELETE_PENDING,
    EXPIRED_ONE_SIDE,
    GROUP_DIFFERS,
)


def repository_group(
    target, repository: str, known: Mapping[str, str]
) -> Optional[str]:
    """The group of the routed repository named ``repository``, or None."""
    if repository in known:
        return known[repository]
    groups = target.group_names()
    return groups[0] if len(groups) == 1 else None


def object_ids(row_id: Optional[str]) -> list[str]:
    """The ObjectIds among an entry's recorded arguments, in order, once each."""
    out: list[str] = []
    for token in (row_id or "").split(","):
        token = token.strip()
        if OBJECT_ID.match(token) and token not in out:
            out.append(token)
    return out


def mongo_holds(
    row: Optional[tuple],
    document: Optional[Mapping[str, Any]],
    deleted_at: Optional[datetime],
    ttl: Optional[tuple],
    now: datetime,
    since: Optional[datetime] = None,
) -> Optional[str]:
    """None when it is proven that Mongo holds what Postgres holds for one
    id, else why not (see the module docstring). ``row`` is ``(checksum,
    updated_at, source, doc)`` or None (no row); ``document`` Mongo's copy or
    None; ``deleted_at`` the latest tombstone of the id in either store.
    ``superseded`` is told apart from ``older_in_mongo`` by timestamps, for
    the opt-in only: Mongo's ``updated_at`` later than the row's and, when
    ``since`` (the entry's time) is given, not before it."""
    if row is not None and row[2] != SOURCE_APP:
        return None  # copied from Mongo: holds no Postgres write
    if row is not None and document is not None:
        if checksum(canonical_document(document)) == row[0]:
            return None
    row_expired = row is not None and expired(from_canonical_document(row[3]), ttl, now)
    doc_expired = document is not None and expired(document, ttl, now)
    row_gone = row is None or row_expired
    doc_gone = document is None or doc_expired
    if row_gone and doc_gone:
        return None  # no live copy on either side
    if row_gone:  # Mongo holds a live copy Postgres does not
        if row_expired:
            return EXPIRED_ONE_SIDE
        if tombstones.is_victim(deleted_at, document.get("updated_at")):
            return DELETE_PENDING
        return MISSING_IN_POSTGRES
    if doc_gone:  # Postgres holds a live row Mongo does not
        if doc_expired:
            return EXPIRED_ONE_SIDE
        if tombstones.is_victim(deleted_at, row[1]):
            return None  # deleted after it was written; Mongo has no copy
        return MISSING_IN_MONGO
    if tombstones.is_victim(deleted_at, row[1]) and tombstones.is_victim(
        deleted_at, document.get("updated_at")
    ):
        return DELETE_PENDING
    mongo_updated = timestamp_of(document.get("updated_at"))
    if (
        mongo_updated is not None
        and row[1] is not None
        and mongo_updated > row[1]
        and (since is None or mongo_updated >= since)
    ):
        return SUPERSEDED
    return OLDER_IN_MONGO


@dataclass
class Entry:
    id: int
    repository: str
    row_ids: list[str]
    created_at: datetime
    group: Optional[str] = None
    reason: Optional[str] = None  # None: resolvable
    superseded: bool = False  # resolvable only because of accept_superseded
    rows: list[dict] = field(default_factory=list)  # named rows not proven


@dataclass
class GroupScan:
    compared: int = 0
    differing: int = 0  # not proven, not superseded: keeps every entry
    superseded: int = 0
    # the earliest Mongo ``updated_at`` of the superseded rows: an entry
    # recorded after it is not superseded by them
    superseded_since: Optional[datetime] = None
    listed: list[dict] = field(default_factory=list)


@dataclass
class Plan:
    """What ``resolve-outbox`` found; ``summary()`` is counts only."""

    groups: list[str]
    accept_superseded: bool = False
    open: int = 0
    entries: list[Entry] = field(default_factory=list)
    out_of_scope: int = 0
    # entries of the repositories of groups served from Postgres only since
    # 4.1 (``Target.retired_repositories``): mirror failures to a Mongo those
    # groups no longer use. Counted apart, never resolved by the proof rule.
    leftover: list[int] = field(default_factory=list)
    scans: dict[str, GroupScan] = field(default_factory=dict)

    @property
    def resolvable(self) -> list[int]:
        return [e.id for e in self.entries if e.reason is None]

    def summary(self) -> dict:
        kept = dict.fromkeys(REASONS, 0)
        for e in self.entries:
            if e.reason is not None:
                kept[e.reason] += 1
        per_group: dict[str, dict] = {}
        for e in self.entries:
            if e.group is None:
                continue
            g = per_group.setdefault(e.group, {"entries": 0, "resolvable": 0})
            g["entries"] += 1
            g["resolvable"] += e.reason is None
        for group, scan in self.scans.items():
            per_group.setdefault(group, {"entries": 0, "resolvable": 0}).update(
                {
                    "rows_compared": scan.compared,
                    "rows_differing": scan.differing,
                    "rows_superseded": scan.superseded,
                }
            )
        return {
            "open": self.open,
            "in_scope": len(self.entries),
            "out_of_scope": self.out_of_scope,
            "postgres_only_leftover": len(self.leftover),
            "resolvable": len(self.resolvable),
            "accept_superseded": self.accept_superseded,
            "resolvable_as_superseded": sum(
                1 for e in self.entries if e.reason is None and e.superseded
            ),
            "kept": kept,
            "groups": per_group,
        }

    def details(self) -> dict:
        """Ids and reasons, for the file the operator asked for (never printed)."""
        return {
            "entries": [
                {
                    "id": e.id,
                    "repository": e.repository,
                    "group": e.group,
                    "created_at": e.created_at.isoformat(),
                    "decision": "resolve" if e.reason is None else "keep",
                    "reason": e.reason,
                    "superseded": e.superseded,
                    "rows": e.rows,
                }
                for e in self.entries
            ],
            "differing_rows": {g: scan.listed for g, scan in self.scans.items()},
        }


def decide(entry: Entry, scan: GroupScan, accept_superseded: bool) -> None:
    """Set ``entry.reason`` (None: resolvable) from its named rows and its
    group's scan."""
    hard = [r for r in entry.rows if r["reason"] != SUPERSEDED]
    if hard:
        entry.reason = hard[0]["reason"]
        return
    if scan.differing:
        entry.reason = GROUP_DIFFERS
        return
    superseded = bool(entry.rows) or bool(scan.superseded)
    if not superseded:
        entry.reason = None
        return
    if scan.superseded and (
        scan.superseded_since is None or scan.superseded_since < entry.created_at
    ):
        # a newer Mongo copy written before the entry: not even superseded
        entry.reason = GROUP_DIFFERS
        return
    if not accept_superseded:
        entry.reason = SUPERSEDED
        return
    entry.reason, entry.superseded = None, True


class OutboxResolver:
    """Plan, then (``--apply``) resolve, the open Postgres-side entries."""

    def __init__(self, runner: Runner):
        self.runner = runner
        self.target = runner.target
        self.table = f'"{self.target.schema}"."mirror_write_failures"'

    def scope(self, groups: Optional[Iterable[str]]) -> list[str]:
        """The groups named, else every group still migrated (a group served
        from Postgres only mirrors nothing to Mongo; the CLI refuses to name
        one)."""
        return list(groups) if groups else self.target.migrating_groups()

    async def plan(
        self,
        groups: Optional[Iterable[str]] = None,
        *,
        accept_superseded: bool = False,
    ) -> Plan:
        wanted = self.scope(groups)
        plan = Plan(groups=wanted, accept_superseded=accept_superseded)
        rows = await self._open_entries()
        plan.open = len(rows)
        if not rows:
            return plan
        known = dict(
            self.target.repository_groups() if self.target.repository_groups else {}
        )
        for entry_id, repository, row_id, created_at in rows:
            retired = self.target.retired_repositories.get(repository)
            if retired is not None and retired in self.target.postgres_only_groups:
                plan.leftover.append(entry_id)
                continue
            group = repository_group(self.target, repository, known)
            entry = Entry(
                id=entry_id,
                repository=repository,
                row_ids=object_ids(row_id),
                created_at=created_at,
                group=group,
            )
            if group is None:
                entry.reason = UNKNOWN_REPOSITORY  # kept, whatever the scope
            elif group not in wanted:
                plan.out_of_scope += 1
                continue
            plan.entries.append(entry)
        for group in wanted:
            entries = [e for e in plan.entries if e.group == group]
            if not entries:
                continue
            scan = await self._scan_group(group)
            plan.scans[group] = scan
            for entry in entries:
                entry.rows = await self._named_rows(group, entry)
                decide(entry, scan, accept_superseded)
        return plan

    async def apply(self, plan: Plan) -> int:
        """Resolve the plan's resolvable entries that are still open. A proof
        stays true: once Mongo holds a row's version, the row's later
        versions are later writes, recorded by entries of their own."""
        return await self._resolve(plan.resolvable)

    async def clear_leftovers(self, plan: Plan) -> int:
        """Resolve the plan's Postgres-only leftovers that are still open:
        only on the operator's explicit request (their groups no longer
        write or read Mongo, so the Mongo write they record has no reader)."""
        return await self._resolve(plan.leftover)

    async def _resolve(self, ids: list[int]) -> int:
        if not ids:
            return 0
        resolved = 0
        async with self.runner.engine.begin() as conn:
            for start in range(0, len(ids), BATCH):
                result = await conn.execute(
                    text(
                        f"UPDATE {self.table} SET resolved_at = now() "
                        "WHERE resolved_at IS NULL AND id = ANY(:ids)"
                    ),
                    {"ids": ids[start : start + BATCH]},
                )
                resolved += result.rowcount or 0
        return resolved

    # -- internals -------------------------------------------------------------
    async def _open_entries(self) -> list[tuple]:
        async with self.runner.engine.connect() as conn:
            if (
                await conn.execute(text(f"SELECT to_regclass('{self.table}')"))
            ).scalar() is None:
                return []
            return list(
                (
                    await conn.execute(
                        text(
                            f"SELECT id, table_name, row_id, created_at FROM {self.table} "
                            "WHERE resolved_at IS NULL ORDER BY id"
                        )
                    )
                ).all()
            )

    @staticmethod
    def _columns(table: Table):
        return (
            table.c.id,
            table.c._bc_checksum,
            table.c.updated_at,
            table.c._bc_source,
            table.c.doc,
        )

    async def _documents(self, name: str, ids: list[str]) -> dict[str, dict]:
        """Mongo's copies of ``ids``, read from its primary."""
        return {
            str(d["_id"]): d
            for d in await on_primary(self.runner.collection(name))
            .find({"_id": {"$in": [ObjectId(i) for i in ids]}})
            .to_list()
        }

    async def _rows(self, table: Table, ids: list[str]) -> dict[str, tuple]:
        async with self.runner.engine.connect() as conn:
            batch = (
                await conn.execute(
                    select(*self._columns(table)).where(table.c.id.in_(ids))
                )
            ).all()
        return {r[0]: tuple(r[1:]) for r in batch}

    def _record(
        self, scan: GroupScan, name: str, row_id: str, reason: str, document, listed
    ) -> int:
        if reason == SUPERSEDED:
            scan.superseded += 1
            at = timestamp_of(document.get("updated_at"))
            if scan.superseded_since is None or at < scan.superseded_since:
                scan.superseded_since = at
        else:
            scan.differing += 1
        if listed < MAX_LISTED:
            scan.listed.append({"collection": name, "id": row_id, "reason": reason})
            return listed + 1
        return listed

    async def _scan_group(self, group: str) -> GroupScan:
        """Every row of the group, in both stores: the Postgres rows the
        application wrote, then the Mongo copies Postgres has no row for."""
        scan = GroupScan()
        now = await self.runner._database_now()
        for name in self.target.collections_of(group):
            table = self.target.tables[name]
            coll = self.runner.collection(name)
            ttl = await self.runner._ttl_of(coll)
            listed = 0
            after = None
            while True:  # Postgres, in id order, a batch at a time
                query = (
                    select(*self._columns(table))
                    .where(table.c._bc_source == SOURCE_APP)
                    .order_by(table.c.id)
                    .limit(BATCH)
                )
                if after is not None:
                    query = query.where(table.c.id > after)
                async with self.runner.engine.connect() as conn:
                    batch = (await conn.execute(query)).all()
                if not batch:
                    break
                after = batch[-1][0]
                rows = {r[0]: tuple(r[1:]) for r in batch}
                ids = list(rows)
                documents = await self._documents(name, ids)
                deleted = await self.runner._tombstones(name, ids)
                scan.compared += len(ids)
                for row_id in ids:
                    document = documents.get(row_id)
                    reason = mongo_holds(
                        rows[row_id], document, deleted.get(row_id), ttl, now
                    )
                    if reason is not None:
                        listed = self._record(
                            scan, name, row_id, reason, document, listed
                        )
            last = None
            while True:  # Mongo, in _id order (ObjectIds only), a batch at a time
                query = (
                    {"_id": {"$gt": last}} if last else {"_id": {"$type": "objectId"}}
                )
                documents = (
                    await on_primary(coll)
                    .find(query)
                    .sort("_id", 1)
                    .limit(BATCH)
                    .to_list()
                )
                if not documents:
                    break
                last = documents[-1]["_id"]
                ids = [str(d["_id"]) for d in documents]
                present = await self._row_ids(table, ids)
                absent = [d for d in documents if str(d["_id"]) not in present]
                if not absent:
                    continue
                absent_ids = [str(d["_id"]) for d in absent]
                deleted = await self.runner._tombstones(name, absent_ids)
                scan.compared += len(absent)
                for document in absent:
                    row_id = str(document["_id"])
                    reason = mongo_holds(None, document, deleted.get(row_id), ttl, now)
                    if reason is not None:
                        listed = self._record(
                            scan, name, row_id, reason, document, listed
                        )
        return scan

    async def _row_ids(self, table: Table, ids: list[str]) -> set[str]:
        async with self.runner.engine.connect() as conn:
            return set(
                (await conn.execute(select(table.c.id).where(table.c.id.in_(ids))))
                .scalars()
                .all()
            )

    async def _named_rows(self, group: str, entry: Entry) -> list[dict]:
        """The rows the entry names that are not proven, with the reason."""
        if not entry.row_ids:
            return []
        now = await self.runner._database_now()
        found = []
        for name in self.target.collections_of(group):
            table = self.target.tables[name]
            ttl = await self.runner._ttl_of(self.runner.collection(name))
            rows = await self._rows(table, entry.row_ids)
            documents = await self._documents(name, entry.row_ids)
            deleted = await self.runner._tombstones(name, entry.row_ids)
            for row_id in entry.row_ids:
                reason = mongo_holds(
                    rows.get(row_id),
                    documents.get(row_id),
                    deleted.get(row_id),
                    ttl,
                    now,
                    since=entry.created_at,
                )
                if reason is not None:
                    found.append({"collection": name, "id": row_id, "reason": reason})
        return found
