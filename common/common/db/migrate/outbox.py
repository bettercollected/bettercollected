"""Resolve Postgres-side outbox entries whose write Mongo already holds.

An entry of ``<schema>.mirror_write_failures`` records a write made while
Postgres was a group's primary whose Mongo mirror failed. Until it is
resolved, ``reconcile`` (``mongo->postgres``) keeps every row the application
wrote, since any of them may be the only copy of that write. After a group is
rolled back to ``dual`` (Mongo first), a Mongo write whose Postgres mirror
failed then leaves an older application row behind that no reconcile
replaces, so ``verify`` is never clean and the entries never resolve (the
runbook's "stuck case"). ``resolve-outbox`` breaks that loop without losing a
write: it resolves an entry only when Mongo holds the same or a newer version
of what Postgres holds.

For each open entry (read once; entries recorded later are never touched):

* its group, from the repository the entry names (the routed repository's
  class name). An unknown repository keeps the entry.
* the rows it names: ``row_id`` is a best-effort list of the write's
  arguments (``common.db.runtime.failure_ids``), so each ObjectId among them
  is looked up in every collection of the group. A row Postgres holds must be
  in Mongo with the same checksum, or with an ``updated_at`` at or after the
  entry's time and later than the row's. A row deleted since (a newer
  tombstone) needs no Mongo copy, but a Mongo copy older than the delete
  keeps the entry (``delete_pending``: ``reconcile`` deletes it first).
* every application-written row of the group: the entry's write may have
  touched rows it does not name (a write by a foreign key, or more ids than
  are recorded), so a single row of the group that Mongo does not hold at the
  same or a newer version (missing, or different without a later
  ``updated_at``) keeps all the group's entries (``group_differs``).

Rows the backfill or a reconcile copied from Mongo (``_bc_source =
'backfill'``) hold Mongo's data, never a Postgres write, so they are not
compared. A copy past its TTL is absent, as for ``verify``.

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
#: blocking row ids kept for the ids file, per collection (the counts are not capped)
MAX_LISTED = 1000

MISSING_IN_MONGO = "missing_in_mongo"
OLDER_IN_MONGO = "older_in_mongo"
DELETE_PENDING = "delete_pending"
GROUP_DIFFERS = "group_differs"
UNKNOWN_REPOSITORY = "unknown_repository"
REASONS = (
    UNKNOWN_REPOSITORY,
    MISSING_IN_MONGO,
    OLDER_IN_MONGO,
    DELETE_PENDING,
    GROUP_DIFFERS,
)


def routed_repository_groups(container: Any) -> dict[str, str]:
    """Repository name -> group for every routed repository a
    dependency-injector container declares. The name is what
    ``RoutingRepository`` reports in a mirror failure: the class of its Mongo
    implementation, else of its Postgres one. A name claimed by two groups is
    left out (its entries are then kept: the group is unknown)."""
    from common.db.routing import RoutingRepository

    found: dict[str, str] = {}
    clashing: set[str] = set()
    for provider in container.providers.values():
        if getattr(provider, "provides", None) is not RoutingRepository:
            continue
        kwargs = getattr(provider, "kwargs", {}) or {}
        group = kwargs.get("group")
        name = _implementation_name(kwargs.get("mongo"))
        if name is None:
            name = _implementation_name(kwargs.get("postgres"), twin=True)
        if not isinstance(group, str) or name is None:
            continue
        if found.get(name, group) != group:
            clashing.add(name)
        found[name] = group
    return {name: group for name, group in found.items() if name not in clashing}


def _implementation_name(provider: Any, *, twin: bool = False) -> Optional[str]:
    if provider is None:
        return None
    provides = getattr(provider, "provides", None)
    if twin:  # Singleton(postgres_repository, TwinClass, sessions, ...)
        args = getattr(provider, "args", ()) or ()
        provides = args[0] if args else None
    return provides.__name__ if isinstance(provides, type) else None


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
    """Why Mongo may not hold what Postgres holds for one id, or None when it
    does. ``row`` is ``(checksum, updated_at, source, doc)`` or None (no
    row); ``document`` Mongo's copy or None; ``deleted_at`` the latest
    tombstone of the id in either store; ``since`` the entry's time, which a
    differing Mongo copy must have reached."""
    if document is not None and expired(document, ttl, now):
        document = None
    if row is None or expired(from_canonical_document(row[3]), ttl, now):
        # nothing in Postgres that Mongo could lack, unless a delete Mongo
        # has not applied yet
        if document is not None and tombstones.is_victim(
            deleted_at, document.get("updated_at")
        ):
            return DELETE_PENDING
        return None
    row_checksum, row_updated, source, _ = row
    if source != SOURCE_APP:
        return None  # copied from Mongo: holds no Postgres write
    if tombstones.is_victim(deleted_at, row_updated):
        # deleted after this row was written: Mongo must not hold an older copy
        if document is not None and tombstones.is_victim(
            deleted_at, document.get("updated_at")
        ):
            return DELETE_PENDING
        return None
    if document is None:
        return MISSING_IN_MONGO
    if checksum(canonical_document(document)) == row_checksum:
        return None
    mongo_updated = timestamp_of(document.get("updated_at"))
    if mongo_updated is None or row_updated is None or not mongo_updated > row_updated:
        return OLDER_IN_MONGO
    if since is not None and mongo_updated < since:
        return OLDER_IN_MONGO
    return None


@dataclass
class Entry:
    id: int
    repository: str
    row_ids: list[str]
    created_at: datetime
    group: Optional[str] = None
    reason: Optional[str] = None  # None: resolvable
    rows: list[dict] = field(default_factory=list)  # named rows that keep it


@dataclass
class Plan:
    """What ``resolve-outbox`` found; ``summary()`` is counts only."""

    groups: list[str]
    open: int = 0
    entries: list[Entry] = field(default_factory=list)
    out_of_scope: int = 0
    scans: dict[str, dict] = field(default_factory=dict)
    blocking: dict[str, list[dict]] = field(default_factory=dict)

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
            per_group.setdefault(group, {"entries": 0, "resolvable": 0}).update(scan)
        return {
            "open": self.open,
            "in_scope": len(self.entries),
            "out_of_scope": self.out_of_scope,
            "resolvable": len(self.resolvable),
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
                    "rows": e.rows,
                }
                for e in self.entries
            ],
            "differing_rows": self.blocking,
        }


class OutboxResolver:
    """Plan, then (``--apply``) resolve, the open Postgres-side entries."""

    def __init__(self, runner: Runner):
        self.runner = runner
        self.target = runner.target
        self.table = f'"{self.target.schema}"."mirror_write_failures"'

    async def plan(self, groups: Optional[Iterable[str]] = None) -> Plan:
        wanted = list(groups) if groups else self.target.group_names()
        plan = Plan(groups=wanted)
        rows = await self._open_entries()
        plan.open = len(rows)
        if not rows:
            return plan
        known = dict(
            self.target.repository_groups() if self.target.repository_groups else {}
        )
        for entry_id, repository, row_id, created_at in rows:
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
            scanned, differing, listed = await self._scan_group(group)
            plan.scans[group] = {"rows_compared": scanned, "rows_differing": differing}
            plan.blocking[group] = listed
            for entry in entries:
                entry.rows = await self._named_rows(group, entry)
                if entry.rows:
                    entry.reason = entry.rows[0]["reason"]
                elif differing:
                    entry.reason = GROUP_DIFFERS
        return plan

    async def apply(self, plan: Plan) -> int:
        """Resolve the plan's resolvable entries (those still open). Once
        Mongo holds a version at least as new as an entry's write it keeps
        doing so (it only gets newer writes), so the plan stays true."""
        ids = plan.resolvable
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

    async def _compare(
        self,
        name: str,
        table: Table,
        ids: list[str],
        rows: Mapping[str, tuple],
        ttl,
        now: datetime,
        since: Optional[datetime] = None,
    ) -> list[tuple[str, str]]:
        """(id, reason) of each of ``ids`` whose Postgres version Mongo may
        not hold, reading Mongo (its primary) and both stores' tombstones."""
        documents = {
            str(d["_id"]): d
            for d in await on_primary(self.runner.collection(name))
            .find({"_id": {"$in": [ObjectId(i) for i in ids]}})
            .to_list()
        }
        deleted = await self.runner._tombstones(name, ids)
        out = []
        for row_id in ids:
            reason = mongo_holds(
                rows.get(row_id),
                documents.get(row_id),
                deleted.get(row_id),
                ttl,
                now,
                since,
            )
            if reason is not None:
                out.append((row_id, reason))
        return out

    @staticmethod
    def _columns(table: Table):
        return (
            table.c.id,
            table.c._bc_checksum,
            table.c.updated_at,
            table.c._bc_source,
            table.c.doc,
        )

    async def _scan_group(self, group: str) -> tuple[int, int, list[dict]]:
        """(application rows compared, rows Mongo may not hold, the listed ones)."""
        now = await self.runner._database_now()
        compared, differing, listed = 0, 0, []
        for name in self.target.collections_of(group):
            table = self.target.tables[name]
            ttl = await self.runner._ttl_of(self.runner.collection(name))
            after, kept_here = None, 0
            while True:  # in id order, a batch at a time: never the whole table
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
                compared += len(rows)
                for row_id, reason in await self._compare(
                    name, table, list(rows), rows, ttl, now
                ):
                    differing += 1
                    if kept_here < MAX_LISTED:
                        kept_here += 1
                        listed.append(
                            {"collection": name, "id": row_id, "reason": reason}
                        )
        return compared, differing, listed

    async def _named_rows(self, group: str, entry: Entry) -> list[dict]:
        """The rows the entry names whose Postgres version Mongo may not hold."""
        if not entry.row_ids:
            return []
        now = await self.runner._database_now()
        found = []
        for name in self.target.collections_of(group):
            table = self.target.tables[name]
            ttl = await self.runner._ttl_of(self.runner.collection(name))
            async with self.runner.engine.connect() as conn:
                batch = (
                    await conn.execute(
                        select(*self._columns(table)).where(
                            table.c.id.in_(entry.row_ids)
                        )
                    )
                ).all()
            rows = {r[0]: tuple(r[1:]) for r in batch}
            for row_id, reason in await self._compare(
                name, table, entry.row_ids, rows, ttl, now, since=entry.created_at
            ):
                found.append({"collection": name, "id": row_id, "reason": reason})
        return found
