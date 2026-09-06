"""Postgres startup/shutdown for the backend (plans/postgres-consolidation.md §4, R1).

Reachability is checked at boot only when the flags involve Postgres at all,
and it is fatal only when a group *serves* from Postgres. A mirror-only
configuration logs and continues: the mirror failing must never take the
application down.
"""

from __future__ import annotations

from loguru import logger

from common.db import ping


async def check_postgres_at_startup(container) -> None:
    flags = container.flags()
    if not flags.requires_postgres():
        return
    engine = container.pg_engine()
    if engine is None:
        raise RuntimeError(
            "DB_*/JOBS_* flags require Postgres but DATABASE_URL is not set"
        )
    try:
        await ping(engine)
        logger.info("Postgres reachable (application database)")
    except Exception as exc:  # noqa: BLE001
        if flags.serves_from_postgres():
            raise RuntimeError(
                "Postgres is unreachable and a repository group serves from it"
            ) from exc
        logger.error(
            "Postgres unreachable at startup; it is only a mirror, continuing: {}",
            type(exc).__name__,
        )


async def dispose_postgres(container) -> None:
    engine = container.pg_engine()
    if engine is not None:
        await engine.dispose()
