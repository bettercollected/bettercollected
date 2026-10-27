"""Refuse to start while a service's data is still only in Mongo.

Every service is served from Postgres only since 4.1; its Mongo collections are
read by nothing but the import (``python -m <service>.migrate backfill``). A stack
upgraded from 4.0 without that import would start with empty tables: no accounts
(and so new accounts for existing emails), no Google credentials, no origins, no
forms. So every process that serves a service's groups checks at startup, per
collection of those groups, and refuses to start when

- the Mongo collection holds at least one document, and
- its import is not finished: either a backfill of it is recorded in
  ``migration_progress`` in any state but ``done`` (interrupted, paused, still
  running, failed: whatever rows it copied, the rest is missing), or no
  backfill is recorded and its Postgres table holds no row.

A finished backfill is the import: once a collection was imported, an empty
table is the application's doing (rows deleted or expired since), not a missing
import. Rows without any recorded backfill are the application's own writes
(a table that was only ever written by the running service).

The probes are cheap: ``SELECT EXISTS`` per table and one read of the backfill
checkpoints first; Mongo is asked only about the collections whose import is not
finished (one ``find_one`` each, plus an estimated count for the message). Without ``MONGO_URI`` (a fresh 4.1 install) Mongo is never contacted.
With ``MONGO_URI`` set, Mongo that cannot be read refuses the start: the check
cannot tell whether data would be lost. Messages name groups, collections and
counts, never a value or the URI.

:data:`OVERRIDE_KEY` (``DB_DISCARD_UNIMPORTED_MONGO_DATA``) lets an operator
start anyway for the groups it names (``all``, or a comma-separated list of the
service's groups), leaving their Mongo data behind; every start with it set logs
a warning per collection it lets through. Never set by default. A service
ignores names of other services' groups (``refdata`` in the auth service's
environment), so one environment file can serve the whole stack; a name no
service knows refuses the start.

Mongo is asked with bounded waits (server selection, connect and socket
timeouts unless the URI sets them, and a cap on the whole probe): a Mongo that
stalls refuses the start like one that is unreachable.

This is the shared core. A service supplies its collection -> group map, its
collection -> table map, its checkpoint table and its migration module; the
backend's (``backend.db.mongo_import_guard``), auth's
(``auth.db.import_guard``) and the Google integration's
(``googleform.db.import_guard``) do.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterable, Mapping, Optional

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from sqlalchemy import Table, exists, select
from sqlalchemy.ext.asyncio import AsyncEngine

from common.db.groups import SERVICE_GROUPS
from common.db.migrate.progress import STATE_DONE

OVERRIDE_KEY = "DB_DISCARD_UNIMPORTED_MONGO_DATA"
#: how long a client of the guard's own waits for Mongo (unless the URI says)
SERVER_SELECTION_TIMEOUT_MS = 10_000
CONNECT_TIMEOUT_MS = 10_000
SOCKET_TIMEOUT_MS = 20_000
#: the whole probe (every ``find_one`` and count together), in seconds
PROBE_TIMEOUT_S = 120.0
#: every group of every service (what an override may name in a shared environment)
KNOWN_GROUPS = tuple(dict.fromkeys(g for gs in SERVICE_GROUPS.values() for g in gs))
#: tables that hold no imported collection (never probed): the migration's own
#: bookkeeping, and the tables that exist only in Postgres (new in 4.2:
#: registration), which 4.0 never had in Mongo
NOT_IMPORTED_TABLES = (
    "mirror_write_failures",
    "migration_progress",
    "registration_services",
    "form_registrations",
    "registration_deliveries",
)


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
    #: collection -> the state of its recorded backfill, when that is not ``done``
    unfinished: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Unimported:
    group: str
    collection: str
    mongo: int  # documents in Mongo (estimated)
    #: the state of the collection's recorded backfill, when there is one that is
    #: not finished; None: no backfill recorded and an empty table
    backfill: Optional[str] = None


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
    """``SELECT EXISTS`` per table, and the state of each recorded backfill."""
    async with engine.connect() as conn:
        has_rows = {
            name
            for name, table in tables.items()
            if (await conn.execute(select(exists().select_from(table)))).scalar()
        }
        recorded = (
            await conn.execute(
                select(progress.c.collection, progress.c.state).where(
                    progress.c.collection.in_(list(tables))
                )
            )
        ).all()
    imported = {name for name, state in recorded if state == STATE_DONE}
    unfinished = {name: state for name, state in recorded if state != STATE_DONE}
    return PostgresState(frozenset(has_rows), frozenset(imported), unfinished)


def is_unimported(name: str, state: PostgresState) -> bool:
    """Whether ``name`` may still be missing data from Mongo: a recorded backfill
    that did not finish, else (none recorded) an empty table."""
    if name in state.unfinished:
        return True
    return name not in state.has_rows and name not in state.imported


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
    env: Mapping[str, str],
    groups: Iterable[str],
    known: Optional[Iterable[str]] = None,
    log: Optional[Any] = None,
) -> frozenset[str]:
    """The groups of ``groups`` that :data:`OVERRIDE_KEY` names (``all``: every
    one). Names of other services' groups (``known``: every group of every
    service) are ignored, with an info log, so one environment file serves the
    whole stack; a name no service knows is refused."""
    groups = tuple(groups)
    known = tuple(dict.fromkeys((*(KNOWN_GROUPS if known is None else known), *groups)))
    raw = (env.get(OVERRIDE_KEY) or "").strip().lower()
    if not raw:
        return frozenset()
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if names == ["all"]:
        return frozenset(groups)
    unknown = [n for n in names if n not in known]
    if unknown:
        raise UnimportedMongoData(
            f"{OVERRIDE_KEY}: unknown group(s) {', '.join(unknown)}; it takes "
            f"'all' or a comma-separated list of {', '.join(known)}"
        )
    other = [n for n in names if n not in groups]
    if other:
        (log or logging.getLogger(__name__)).info(
            f"{OVERRIDE_KEY} names {', '.join(other)}, which "
            f"{'is a group' if len(other) == 1 else 'are groups'} of other services: "
            f"ignored here (this service has {', '.join(groups)})"
        )
    return frozenset(n for n in names if n in groups)


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
    # bounded waits, unless the operator's URI sets them
    options = {}
    lowered = uri.lower()
    for option, default in (
        ("serverSelectionTimeoutMS", SERVER_SELECTION_TIMEOUT_MS),
        ("connectTimeoutMS", CONNECT_TIMEOUT_MS),
        ("socketTimeoutMS", SOCKET_TIMEOUT_MS),
    ):
        if option.lower() not in lowered:
            options[option] = default
    own = AsyncMongoClient(uri, **options)
    try:
        yield own[name]
    finally:
        await own.close()


def _listed(items: Iterable[Unimported]) -> str:
    return "; ".join(
        f"{u.group}: {u.collection} ({u.mongo} in Mongo, import unfinished: "
        f"backfill {u.backfill})"
        if u.backfill
        else f"{u.group}: {u.collection} ({u.mongo} in Mongo, 0 in Postgres)"
        for u in items
    )


def import_command(migrate_module: str, groups: Iterable[str]) -> str:
    return f"python -m {migrate_module} --group {','.join(groups)} backfill"


async def _probe(
    client: Optional[Any],
    uri: str,
    database: str,
    candidates: list[str],
    result: GuardResult,
    log: Any,
    groups: tuple[str, ...],
) -> Optional[dict[str, int]]:
    """The candidates' document counts, or None when there is no Mongo to ask."""
    async with mongo_database(client, uri, database) as db:
        if db is None:
            log.info(
                f"MONGO_URI is not set: no Mongo data to import for {', '.join(groups)}"
            )
            return None
        result.mongo_checked = True
        return await mongo_documents(db, candidates)


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
    discard = override_groups(env, groups, log=log)
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
    candidates = [c for c in collections if is_unimported(c, state)]
    result = GuardResult()
    if not candidates:
        return result
    failure = None
    try:
        found = await asyncio.wait_for(
            _probe(client, uri, database, candidates, result, log, groups),
            PROBE_TIMEOUT_S,
        )
    except (PyMongoError, ValueError, TimeoutError, asyncio.TimeoutError, OSError) as exc:
        failure = type(exc).__name__  # the class only: a message may carry the host
    if failure is not None:
        # raised outside the handler: nothing chains the driver's error (it names
        # the host and port) into the traceback
        raise UnimportedMongoData(
            f"MONGO_URI is set but Mongo could not be read ({failure}), so "
            f"it is unknown whether the {', '.join(groups)} groups have data there "
            "that was never imported into Postgres. Make Mongo reachable, or, once "
            "it holds nothing to keep, remove MONGO_URI (see "
            "docs/postgres-cutover-runbook.md, 'Upgrading to 4.1')."
        )
    if found is None:
        return result
    for name, count in found.items():
        item = Unimported(
            collections[name], name, count, state.unfinished.get(name)
        )
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
