"""Apply procrastinate's schema into the ``jobs`` schema, once.

``python -m backend.jobs.schema`` — run at deploy after Alembic (deploy.sh),
as the backend's role (bc_app owns ``jobs``). Idempotent: a no-op when the
queue table already exists, so it cannot hang or half-apply a second time.
With ``DB_AUTO_MIGRATE=true`` the backend applies it itself at startup under an
advisory lock (:data:`JOBS_SCHEMA`, wired in ``backend.db.startup``).
"""

from __future__ import annotations

import asyncio
import sys

from procrastinate import App
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.jobs.app import app, build_connector, postgres_jobs_enabled
from common.db import AuxiliarySchema

QUEUE_TABLE = "jobs.procrastinate_jobs"


async def ensure_schema(jobs_app: App = app) -> bool:
    """Returns True when the schema was applied, False when it was present."""
    async with jobs_app.open_async():
        row = await jobs_app.connector.execute_query_one_async(
            f"SELECT to_regclass('{QUEUE_TABLE}') AS queue_table"
        )
        if row["queue_table"] is not None:
            return False
        await jobs_app.schema_manager.apply_schema_async()
        return True


async def queue_table_present(conn: AsyncConnection) -> bool:
    found = await conn.scalar(text("SELECT to_regclass(:t)"), {"t": QUEUE_TABLE})
    return found is not None


async def apply_schema(database_url: str) -> bool:
    """On a connector of its own: the process-wide app is opened separately."""
    return await ensure_schema(App(connector=build_connector(database_url)))


JOBS_SCHEMA = AuxiliarySchema(
    name="jobs",
    needed=postgres_jobs_enabled,
    present=queue_table_present,
    apply=apply_schema,
    fix="Apply procrastinate's schema (`python -m backend.jobs.schema`, as deploy.sh does).",
)


if __name__ == "__main__":
    applied = asyncio.run(ensure_schema())
    print("procrastinate schema applied" if applied else "procrastinate schema present")
    sys.exit(0)
