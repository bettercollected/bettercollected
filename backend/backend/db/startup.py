"""Postgres startup/shutdown for the backend, over :mod:`common.db.runtime`.

Reachability is fatal only when a group *serves* from Postgres; a mirror-only
configuration logs and continues. The effective flags are logged at boot so a
flip is auditable in the deploy history.
"""

from __future__ import annotations

import json

from loguru import logger

from backend.db.groups import MONGO_JOINS
from backend.jobs.app import JOB_NAMES
from common.db import check_postgres_at_startup as _check
from common.db import dispose_engine

GROUPS = ("refdata", "identity", "forms", "responses", "actions", "ai", "analytics")


async def check_postgres_at_startup(container) -> None:
    flags = container.flags()
    logger.info(
        "persistence flags: {}",
        json.dumps(flags.describe(GROUPS, JOB_NAMES), sort_keys=True),
    )
    await _check(flags, container.pg_engine())


async def dispose_postgres(container) -> None:
    await dispose_engine(container.pg_engine())
