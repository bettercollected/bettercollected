"""Postgres startup/shutdown for the backend, over :mod:`common.db.runtime`.

Postgres is the only store: it must be configured and reachable, else startup
is refused. A reachable database must carry the ``app`` schema at the code's
Alembic head (and procrastinate's ``jobs`` tables when a job kind runs on
Postgres), else startup is refused; ``DB_AUTO_MIGRATE=true`` applies both
first (:mod:`common.db.schema_guard`). The effective flags are logged at boot
so a change is auditable in the deploy history.

The backend never connects to Mongo. Once the schema is ready, the start is
refused while a Postgres-only group's data sits in Mongo without having been
imported (:mod:`backend.db.mongo_import_guard`), which looks at Mongo with a
client of its own while ``MONGO_URI`` is set.
"""

from __future__ import annotations

import json

from loguru import logger

import backend
from backend.db.base import SCHEMA
from backend.db.mongo_import_guard import (
    check_unimported_mongo_data,
    mongo_uri_configured,
)
from backend.jobs.app import JOB_NAMES
from backend.jobs.schema import JOBS_SCHEMA
from common.db import MigrationTarget
from common.db import check_postgres_at_startup as _check
from common.db import dispose_engine

MIGRATIONS = MigrationTarget.for_package(backend, SCHEMA, service="backend")


async def check_postgres_at_startup(container) -> None:
    flags = container.flags()
    logger.info(
        "persistence flags: {}",
        json.dumps(flags.describe(JOB_NAMES), sort_keys=True),
    )
    await _check(flags, container.pg_engine(), MIGRATIONS, (JOBS_SCHEMA,))
    await check_mongo_import(container)


async def check_mongo_import(container) -> None:
    """:func:`backend.db.mongo_import_guard.check_unimported_mongo_data` on the
    container's Postgres engine and, while ``MONGO_URI`` is set, a Mongo client
    of the guard's own."""
    from backend.config import settings

    await check_unimported_mongo_data(
        container.pg_engine(),
        client=None,
        uri=mongo_uri_configured(settings.mongo_settings),
        database=settings.mongo_settings.DB,
    )


async def dispose_postgres(container) -> None:
    await dispose_engine(container.pg_engine())
