"""Refuse to start while a Postgres-only group's data is still only in Mongo.

The groups of :data:`backend.db.groups.POSTGRES_ONLY_GROUPS` are served from
Postgres only since 4.1; their Mongo collections are read by nothing but the
import (``python -m backend.migrate --group <g> backfill``). A stack upgraded
from 4.0 without that import would start with empty tables: no allowed
origins, no coupon codes, no price suggestions, no AI memories, no actions.
So every process that serves these groups checks at startup, per collection
of those groups (``COLLECTION_GROUPS``), and refuses to start when

- the Mongo collection holds at least one document, and
- its import is not finished: a backfill of it is recorded
  (``migration_progress``) in any state but ``done`` (interrupted, paused,
  running, failed: whatever rows it copied, the rest is missing), or none is
  recorded and its Postgres table holds no row.

A finished backfill is the import: once a collection was imported, an empty
table is the application's doing (rows deleted or expired since), not a missing
import.

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

The checks themselves are shared with auth and the Google integration
(:mod:`common.db.migrate.import_guard`); this module supplies the backend's
groups, tables and migration CLI.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping, Optional

from loguru import logger
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.db.groups import COLLECTION_GROUPS, POSTGRES_ONLY_GROUPS
from common.db.migrate import import_guard as _core
from common.db.migrate.import_guard import (  # noqa: F401 — the shared core's API
    OVERRIDE_KEY,
    SERVER_SELECTION_TIMEOUT_MS,
    GuardResult,
    PostgresState,
    Unimported,
    UnimportedMongoData,
    mongo_database as _database,
    mongo_documents,
    mongo_uri_configured,
    override_groups as _override_groups,
    postgres_state,
)

MIGRATE_MODULE = "backend.migrate"


def override_groups(
    env: Mapping[str, str], groups: Iterable[str] = POSTGRES_ONLY_GROUPS
) -> frozenset[str]:
    """The groups :data:`OVERRIDE_KEY` names (``all``: every one)."""
    return _override_groups(env, groups)


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

    return _core.collection_tables(Base)


def import_command(groups: Iterable[str]) -> str:
    return _core.import_command(MIGRATE_MODULE, groups)


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
    """:func:`common.db.migrate.import_guard.check_unimported_mongo_data` for
    the backend's ``groups``.

    ``client``: the process's connected Mongo client, when a repository group
    uses Mongo (else None); ``uri``: the configured ``MONGO_URI`` (``""``:
    none); ``state``: the Postgres side, probed on ``engine`` when not given."""
    groups = tuple(groups)
    tables = progress = None
    if state is None:
        from backend.db.models import MigrationProgress

        tables = collection_tables()
        progress = MigrationProgress.__table__
    return await _core.check_unimported_mongo_data(
        engine,
        collections=guarded_collections(groups),
        tables=tables,
        progress=progress,
        migrate_module=MIGRATE_MODULE,
        client=client,
        uri=uri,
        database=database,
        groups=groups,
        env=env,
        state=state,
        log=logger,
    )
