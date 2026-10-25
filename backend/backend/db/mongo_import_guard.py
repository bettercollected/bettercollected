"""Refuse to start while a Postgres-only group's data is still only in Mongo.

The groups of :data:`backend.db.groups.POSTGRES_ONLY_GROUPS` are served from
Postgres only since 4.1; their Mongo collections are read by nothing but the
import (``python -m backend.migrate --group <g> backfill``). A stack upgraded
from 4.0 without that import would start with empty tables: no allowed
origins, no coupon codes, no price suggestions, no AI memories, no actions.
So every process that serves these groups checks at startup, per collection
of those groups (``COLLECTION_GROUPS``), and refuses to start when

- the Mongo collection holds at least one document,
- its Postgres table holds no row, and
- no finished backfill of it is recorded (``migration_progress``): once a
  collection was imported, an empty table is the application's doing (rows
  deleted or expired since), not a missing import.

The probes are cheap: ``SELECT EXISTS`` per table and one read of the
backfill checkpoints first; Mongo is asked only about the collections whose
table is empty and not imported (one ``find_one`` each, plus an estimated
count for the message). Without ``MONGO_URI`` (a fresh 4.1 install), and
while no repository group uses Mongo, Mongo is never contacted. With
``MONGO_URI`` set, Mongo that cannot be read refuses the start: the check
cannot tell whether data would be lost.

:data:`OVERRIDE_KEY` (``DB_DISCARD_UNIMPORTED_MONGO_DATA``) lets an operator
start anyway for the groups it names (``all``, or a comma-separated list),
leaving their Mongo data behind; every start with it set logs a warning per
collection it lets through. Never set by default.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterable, Mapping, Optional

from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from sqlalchemy import Table, exists, select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.db.groups import COLLECTION_GROUPS, POSTGRES_ONLY_GROUPS
from common.db.migrate.progress import STATE_DONE

OVERRIDE_KEY = "DB_DISCARD_UNIMPORTED_MONGO_DATA"
#: how long a client of the guard's own waits for Mongo (unless the URI says)
SERVER_SELECTION_TIMEOUT_MS = 10_000


class UnimportedMongoData(RuntimeError):
    """A Postgres-only group's data is in Mongo but was not imported, or
    Mongo, configured, could not be read."""


def guarded_collections(
    groups: Iterable[str] = POSTGRES_ONLY_GROUPS,
) -> dict[str, str]:
    """Mongo collection -> its group, for the collections of ``groups``."""
    wanted = set(groups)
    return {c: g for c, g in COLLECTION_GROUPS.items() if g in wanted}


def collection_tables() -> dict[str, Table]:
    """Mongo collection -> the Postgres table holding it (every backend row
    that has one; the migration CLI migrates these)."""
    import backend.db.models  # noqa: F401 — registers every row
    from backend.db.base import Base

    return {
        mapper.class_.mongo_collection(): mapper.local_table
        for mapper in Base.registry.mappers
        if hasattr(mapper.class_, "mongo_collection")
        and mapper.local_table.name
        not in ("mirror_write_failures", "migration_progress")
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


def override_groups(
    env: Mapping[str, str], groups: Iterable[str] = POSTGRES_ONLY_GROUPS
) -> frozenset[str]:
    """The groups :data:`OVERRIDE_KEY` names (``all``: every one)."""
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
async def _database(
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


def import_command(groups: Iterable[str]) -> str:
    return f"python -m backend.migrate --group {','.join(groups)} backfill"


async def check_unimported_mongo_data(
    engine: AsyncEngine,
    *,
    client: Optional[Any],
    uri: str,
    database: str,
    env: Mapping[str, str] = os.environ,
    groups: Iterable[str] = POSTGRES_ONLY_GROUPS,
    state: Optional[PostgresState] = None,
) -> GuardResult:
    """Raise :class:`UnimportedMongoData` when a guarded collection holds Mongo
    data that Postgres does not (see the module docstring).

    ``client``: the process's connected Mongo client, when a repository group
    uses Mongo (else None); ``uri``: the configured ``MONGO_URI`` (``""``:
    none); ``state``: the Postgres side, probed on ``engine`` when not given."""
    groups = tuple(groups)
    discard = override_groups(env, groups)
    if discard:
        logger.warning(
            "{} is set ({}): Mongo data of these groups that was never imported "
            "into Postgres is left behind. Remove it once the start is through.",
            OVERRIDE_KEY,
            ", ".join(sorted(discard)),
        )
    collections = guarded_collections(groups)
    if state is None:
        from backend.db.models import MigrationProgress

        tables = collection_tables()
        # a collection without a table has nothing to import into
        collections = {c: g for c, g in collections.items() if c in tables}
        state = await postgres_state(
            engine,
            {c: tables[c] for c in collections},
            MigrationProgress.__table__,
        )
    candidates = [
        c for c in collections if c not in state.has_rows and c not in state.imported
    ]
    result = GuardResult()
    if not candidates:
        return result
    try:
        async with _database(client, uri, database) as db:
            if db is None:
                logger.info(
                    "MONGO_URI is not set: no Mongo data to import for {}",
                    ", ".join(groups),
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
        logger.warning(
            "{}: starting WITHOUT the Mongo data of {} ({}, {} documents): it was "
            "never imported into Postgres",
            OVERRIDE_KEY,
            item.group,
            item.collection,
            item.mongo,
        )
    if result.blocking:
        blocked = [g for g in groups if any(u.group == g for u in result.blocking)]
        raise UnimportedMongoData(
            "Refusing to start: the "
            f"{', '.join(blocked)} group(s) are served from Postgres only since 4.1, "
            "and Mongo holds data of theirs that was never imported into Postgres: "
            f"{_listed(result.blocking)}. Import it with "
            f"`{import_command(blocked)}` (then `python -m backend.migrate status`), "
            f"and start again. To discard that data instead, set {OVERRIDE_KEY}="
            f"{','.join(blocked)} (docs/postgres-cutover-runbook.md, 'Upgrading to 4.1')."
        )
    return result
