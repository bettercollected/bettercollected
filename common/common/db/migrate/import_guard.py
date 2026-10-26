"""Refuse to start while a service's data is still only in Mongo.

Every service is served from Postgres only since 4.1; its Mongo collections are
read by nothing but the import (``python -m <service>.migrate backfill``). A stack
upgraded from 4.0 without that import would start with empty tables: no accounts
(and so new accounts for existing emails), no Google credentials, no origins, no
forms. So every process that serves a service's groups checks at startup, per
collection of those groups, and refuses to start when

- the Mongo collection holds at least one document,
- its Postgres table holds no row, and
- no finished backfill of it is recorded (``migration_progress``): once a
  collection was imported, an empty table is the application's doing (rows
  deleted or expired since), not a missing import.

The probes are cheap: ``SELECT EXISTS`` per table and one read of the backfill
checkpoints first; Mongo is asked only about the collections whose table is
empty and not imported (one ``find_one`` each, plus an estimated count for the
message). Without ``MONGO_URI`` (a fresh 4.1 install) Mongo is never contacted.
With ``MONGO_URI`` set, Mongo that cannot be read refuses the start: the check
cannot tell whether data would be lost. Messages name groups, collections and
counts, never a value or the URI.

:data:`OVERRIDE_KEY` (``DB_DISCARD_UNIMPORTED_MONGO_DATA``) lets an operator
start anyway for the groups it names (``all``, or a comma-separated list of the
service's groups), leaving their Mongo data behind; every start with it set logs
a warning per collection it lets through. Never set by default.

This is the shared core. A service supplies its collection -> group map, its
collection -> table map, its checkpoint table and its migration module; the
backend's (``backend.db.mongo_import_guard``), auth's
(``auth.db.import_guard``) and the Google integration's
(``googleform.db.import_guard``) do.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterable, Mapping, Optional

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from sqlalchemy import Table, exists, select
from sqlalchemy.ext.asyncio import AsyncEngine

from common.db.migrate.progress import STATE_DONE

OVERRIDE_KEY = "DB_DISCARD_UNIMPORTED_MONGO_DATA"
#: how long a client of the guard's own waits for Mongo (unless the URI says)
SERVER_SELECTION_TIMEOUT_MS = 10_000
#: tables that hold no imported collection (never probed)
NOT_IMPORTED_TABLES = ("mirror_write_failures", "migration_progress")


class UnimportedMongoData(RuntimeError):
    """A service's data is in Mongo but was not imported, or Mongo, configured,
    could not be read."""


def collection_tables(base: Any) -> dict[str, Table]:
    """Mongo collection -> the Postgres table holding it, for every row of the
    declarative ``base`` that has one (what the service's migration CLI
    migrates). The service's models must be imported."""
    return {
        mapper.class_.mongo_collection(): mapper.local_table
        for mapper in base.registry.mappers
        if hasattr(mapper.class_, "mongo_collection")
        and mapper.local_table.name not in NOT_IMPORTED_TABLES
    }


@dataclass(frozen=True)
class PostgresState:
    """Which guarded collections' tables have rows, and which were imported."""

    has_rows: frozenset[str] = frozenset()
    imported: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Unimported:
    group: str
    collection: str
    mongo: int  # documents in Mongo (estimated)


@dataclass
class GuardResult:
    #: Mongo data that blocks the start
    blocking: list[Unimported] = field(default_factory=list)
    #: Mongo data left behind on the operator's say-so (OVERRIDE_KEY)
    discarded: list[Unimported] = field(default_factory=list)
    #: whether Mongo was asked at all
    mongo_checked: bool = False


async def postgres_state(
    engine: AsyncEngine, tables: Mapping[str, Table], progress: Table
) -> PostgresState:
    """``SELECT EXISTS`` per table, and the collections with a finished backfill."""
    async with engine.connect() as conn:
        has_rows = {
            name
            for name, table in tables.items()
            if (await conn.execute(select(exists().select_from(table)))).scalar()
        }
        imported = set(
            (
                await conn.execute(
                    select(progress.c.collection).where(
                        progress.c.collection.in_(list(tables)),
                        progress.c.state == STATE_DONE,
                    )
                )
            ).scalars()
        )
    return PostgresState(frozenset(has_rows), frozenset(imported))


async def mongo_documents(database: Any, collections: Iterable[str]) -> dict[str, int]:
    """Collection -> its (estimated) document count, for the non-empty ones."""
    found: dict[str, int] = {}
    for name in collections:
        coll = database[name]
        if await coll.find_one({}, {"_id": 1}) is None:
            continue
        # metadata only; at least 1, since a document was just found
        found[name] = max(1, await coll.estimated_document_count())
    return found


def override_groups(env: Mapping[str, str], groups: Iterable[str]) -> frozenset[str]:
    """The groups :data:`OVERRIDE_KEY` names (``all``: every one of ``groups``)."""
    groups = tuple(groups)
    raw = (env.get(OVERRIDE_KEY) or "").strip().lower()
    if not raw:
        return frozenset()
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if names == ["all"]:
        return frozenset(groups)
    unknown = [n for n in names if n not in groups]
    if unknown:
        raise UnimportedMongoData(
            f"{OVERRIDE_KEY}: unknown group(s) {', '.join(unknown)}; it takes "
            f"'all' or a comma-separated list of {', '.join(groups)}"
        )
    return frozenset(names)


def mongo_uri_configured(settings_obj: Any) -> str:
    """The ``MONGO_URI`` an operator set (environment or settings store), or
    ``""`` when only the built-in default applies."""
    if "URI" not in settings_obj.model_fields_set:
        return ""
    return (settings_obj.URI or "").strip()


@asynccontextmanager
async def mongo_database(
    client: Optional[Any], uri: str, name: str
) -> AsyncIterator[Optional[Any]]:
    """The Mongo database to probe: on the process's connected client when it
    has one, else on a client of its own on ``uri``; None without either."""
    if client is not None:
        yield client[name]
        return
    if not uri:
        yield None
        return
    options = {}
    if "serverselectiontimeoutms" not in uri.lower():
        options["serverSelectionTimeoutMS"] = SERVER_SELECTION_TIMEOUT_MS
    own = AsyncMongoClient(uri, **options)
    try:
        yield own[name]
    finally:
        await own.close()


def _listed(items: Iterable[Unimported]) -> str:
    return "; ".join(
        f"{u.group}: {u.collection} ({u.mongo} in Mongo, 0 in Postgres)" for u in items
    )


def import_command(migrate_module: str, groups: Iterable[str]) -> str:
    return f"python -m {migrate_module} --group {','.join(groups)} backfill"


async def check_unimported_mongo_data(
    engine: AsyncEngine,
    *,
    collections: Mapping[str, str],
    tables: Optional[Mapping[str, Table]] = None,
    progress: Optional[Table] = None,
    migrate_module: str,
    client: Optional[Any],
    uri: str,
    database: str,
    groups: Iterable[str],
    env: Mapping[str, str] = os.environ,
    state: Optional[PostgresState] = None,
    log: Optional[Any] = None,
) -> GuardResult:
    """Raise :class:`UnimportedMongoData` when a guarded collection holds Mongo
    data that Postgres does not (see the module docstring).

    ``collections``: guarded Mongo collection -> its group; ``tables``: Mongo
    collection -> Postgres table, and ``progress``: the checkpoint table (both
    needed unless ``state`` is given); ``migrate_module``: the service's
    migration CLI, named in the message (``backend.migrate``); ``client``: the
    process's connected Mongo client, when one is (else None); ``uri``: the
    configured ``MONGO_URI`` (``""``: none); ``groups``: the service's groups
    (what the override may name); ``state``: the Postgres side, probed on
    ``engine`` when not given; ``log``: a ``warning``/``info`` logger (default:
    this module's)."""
    log = log or logging.getLogger(__name__)
    groups = tuple(groups)
    discard = override_groups(env, groups)
    if discard:
        log.warning(
            f"{OVERRIDE_KEY} is set ({', '.join(sorted(discard))}): Mongo data of "
            "these groups that was never imported into Postgres is left behind. "
            "Remove it once the start is through."
        )
    if state is None:
        if tables is None or progress is None:
            raise ValueError("tables and progress are needed without a state")
        # a collection without a table has nothing to import into
        collections = {c: g for c, g in collections.items() if c in tables}
        state = await postgres_state(
            engine, {c: tables[c] for c in collections}, progress
        )
    candidates = [
        c for c in collections if c not in state.has_rows and c not in state.imported
    ]
    result = GuardResult()
    if not candidates:
        return result
    try:
        async with mongo_database(client, uri, database) as db:
            if db is None:
                log.info(
                    f"MONGO_URI is not set: no Mongo data to import for {', '.join(groups)}"
                )
                return result
            result.mongo_checked = True
            found = await mongo_documents(db, candidates)
    except PyMongoError as exc:
        raise UnimportedMongoData(
            f"MONGO_URI is set but Mongo could not be read ({type(exc).__name__}), so "
            f"it is unknown whether the {', '.join(groups)} groups have data there "
            "that was never imported into Postgres. Make Mongo reachable, or, once "
            "it holds nothing to keep, remove MONGO_URI (see "
            "docs/postgres-cutover-runbook.md, 'Upgrading to 4.1')."
        ) from exc
    for name, count in found.items():
        item = Unimported(collections[name], name, count)
        (result.discarded if item.group in discard else result.blocking).append(item)
    for item in result.discarded:
        log.warning(
            f"{OVERRIDE_KEY}: starting WITHOUT the Mongo data of {item.group} "
            f"({item.collection}, {item.mongo} documents): it was never imported "
            "into Postgres"
        )
    if result.blocking:
        blocked = [g for g in groups if any(u.group == g for u in result.blocking)]
        raise UnimportedMongoData(
            "Refusing to start: the "
            f"{', '.join(blocked)} group(s) are served from Postgres only since 4.1, "
            "and Mongo holds data of theirs that was never imported into Postgres: "
            f"{_listed(result.blocking)}. Import it with "
            f"`{import_command(migrate_module, blocked)}` (then "
            f"`python -m {migrate_module} status`), "
            f"and start again. To discard that data instead, set {OVERRIDE_KEY}="
            f"{','.join(blocked)} (docs/postgres-cutover-runbook.md, 'Upgrading to 4.1')."
        )
    return result
