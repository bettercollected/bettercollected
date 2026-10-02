"""Postgres startup/shutdown for the backend, over :mod:`common.db.runtime`.

Reachability is fatal only when a group *serves* from Postgres; a mirror-only
configuration logs and continues. A reachable database must carry the ``app``
schema at the code's Alembic head (and procrastinate's ``jobs`` tables when a
job kind runs on Postgres), else startup is refused; ``DB_AUTO_MIGRATE=true``
applies both first (:mod:`common.db.schema_guard`). The effective flags are
logged at boot so a flip is auditable in the deploy history.
"""

from __future__ import annotations

import json

from loguru import logger

import backend
from backend.db.base import SCHEMA
from backend.jobs.app import JOB_NAMES
from backend.jobs.schema import JOBS_SCHEMA
from common.db import MigrationTarget
from common.db import check_postgres_at_startup as _check
from common.db import dispose_engine

GROUPS = ("refdata", "identity", "forms", "responses", "actions", "ai", "analytics")
MIGRATIONS = MigrationTarget.for_package(backend, SCHEMA, service="backend")


async def check_postgres_at_startup(container) -> None:
    flags = container.flags()
    logger.info(
        "persistence flags: {}",
        json.dumps(flags.describe(GROUPS, JOB_NAMES), sort_keys=True),
    )
    await _check(flags, container.pg_engine(), MIGRATIONS, (JOBS_SCHEMA,))


async def dispose_postgres(container) -> None:
    await dispose_engine(container.pg_engine())
