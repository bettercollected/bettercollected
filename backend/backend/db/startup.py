"""Postgres startup/shutdown for the backend, over :mod:`common.db.runtime`.

Reachability is fatal only when a group *serves* from Postgres; a mirror-only
configuration logs and continues. A reachable database must carry the ``app``
schema at the code's Alembic head (and procrastinate's ``jobs`` tables when a
job kind runs on Postgres), else startup is refused; ``DB_AUTO_MIGRATE=true``
applies both first (:mod:`common.db.schema_guard`). The effective flags are
logged at boot so a flip is auditable in the deploy history.

Mongo is connected only while a repository group uses it
(:func:`mongo_required`); once every group is on Postgres the backend and its
job worker start without it (:mod:`common.db.mongo`).
"""

from __future__ import annotations

import json

from loguru import logger

import backend
from backend.db.base import SCHEMA
from backend.db.groups import GROUPS
from backend.jobs.app import JOB_NAMES
from backend.jobs.schema import JOBS_SCHEMA
from common.db import MigrationTarget
from common.db import check_postgres_at_startup as _check
from common.db import dispose_engine
from common.db import mongo_required as _mongo_required

MIGRATIONS = MigrationTarget.for_package(backend, SCHEMA, service="backend")


def mongo_required(container) -> bool:
    """Whether any backend repository group reads, writes or shadow-reads Mongo."""
    return _mongo_required(container.flags(), GROUPS)


async def check_postgres_at_startup(container) -> None:
    flags = container.flags()
    logger.info(
        "persistence flags: {}",
        json.dumps(flags.describe(GROUPS, JOB_NAMES), sort_keys=True),
    )
    await _check(flags, container.pg_engine(), MIGRATIONS, (JOBS_SCHEMA,))


async def dispose_postgres(container) -> None:
    await dispose_engine(container.pg_engine())
