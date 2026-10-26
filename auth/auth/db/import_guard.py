"""Refuse to start while the 4.0 auth data is still only in Mongo.

auth is served from Postgres only since 4.1. A stack upgraded from 4.0 whose
import (``python -m auth.migrate --group auth backfill``) did not finish would
start on an empty or partial ``auth.users``, and sign-in would create new
accounts for emails that already have one. The checks are shared with the other
services (:mod:`common.db.migrate.import_guard`); this module supplies auth's
collections and migration CLI. It lives beside the rows, not under ``app``:
the import CLI reads the same collection map and must not boot the application.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine

import auth.db.models  # noqa: F401 — registers every row
from auth.db.base import Base
from auth.db.models import MigrationProgress
from common.db.migrate import import_guard as core
from common.db.migrate.import_guard import (  # noqa: F401 — the shared core's API
    OVERRIDE_KEY,
    GuardResult,
    UnimportedMongoData,
)

GROUP = "auth"
MIGRATE_MODULE = "auth.migrate"

log = logging.getLogger(__name__)


def collection_tables() -> dict[str, Table]:
    """Mongo collection -> the Postgres table holding it (what ``python -m
    auth.migrate`` migrates and this guard checks)."""
    return core.collection_tables(Base)


async def check_mongo_import(engine: AsyncEngine, *, client: Any = None) -> GuardResult:
    """:func:`common.db.migrate.import_guard.check_unimported_mongo_data` for
    the ``auth`` group, on the configured ``MONGO_URI`` (none: nothing to
    check). Raises :class:`UnimportedMongoData` to refuse the start."""
    from auth.config import settings

    tables = collection_tables()
    return await core.check_unimported_mongo_data(
        engine,
        collections={c: GROUP for c in tables},
        tables=tables,
        progress=MigrationProgress.__table__,
        migrate_module=MIGRATE_MODULE,
        client=client,
        uri=core.mongo_uri_configured(settings.mongo_settings),
        database=settings.mongo_settings.DB,
        groups=(GROUP,),
        log=log,
    )
