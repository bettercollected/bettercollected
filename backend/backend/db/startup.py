"""Postgres startup/shutdown for the backend, over :mod:`common.db.runtime`.

Postgres is the only store: it must be configured and reachable, else startup
is refused. A reachable database must carry the ``app`` schema at the code's
Alembic head (and procrastinate's ``jobs`` tables when a job kind runs on
Postgres), else startup is refused; ``DB_AUTO_MIGRATE=true`` applies both
first (:mod:`common.db.schema_guard`), then scrubs the action jobs 4.1.x left
with response data in them. The effective flags are logged at boot so a change
is auditable in the deploy history.

The backend never connects to Mongo. Once the schema is ready, the start is
refused while a Postgres-only group's data sits in Mongo without having been
imported (:mod:`backend.db.mongo_import_guard`), which looks at Mongo with a
client of its own while ``MONGO_URI`` is set.
"""

from __future__ import annotations

import json
import os

from loguru import logger

import backend
from backend.db.base import SCHEMA
from backend.db.mongo_import_guard import (
    check_unimported_mongo_data,
    mongo_uri_configured,
)
from backend.jobs.app import JOB_NAMES, postgres_jobs_enabled
from backend.jobs.schema import JOBS_SCHEMA, scrub_at
from common.db import MigrationTarget, auto_migrate_enabled
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
    await scrub_legacy_action_jobs(flags, container.pg_engine())
    await check_mongo_import(container)


async def scrub_legacy_action_jobs(flags, engine, env=os.environ) -> None:
    """With ``DB_AUTO_MIGRATE`` on, remove the response data that 4.1.x left in
    the actions queue, as ``python -m backend.jobs.schema`` does at deploy
    (:mod:`backend.jobs.legacy`): a stack that upgrades by swapping images never
    runs that command. Idempotent, counts only in the log. A failure is logged
    and does not stop the start; the next start tries again."""
    if not auto_migrate_enabled(env) or engine is None:
        return
    if not postgres_jobs_enabled(flags):
        return
    try:
        await scrub_at(engine.url.render_as_string(hide_password=False))
    except Exception as exc:  # noqa: BLE001 - never block the start on the scrub
        logger.warning(
            "legacy action jobs: the scrub at startup failed ({}); "
            "run `python -m backend.jobs.schema`",
            type(exc).__name__,
        )


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
