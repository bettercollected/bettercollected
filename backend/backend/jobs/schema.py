"""Apply procrastinate's schema into the ``jobs`` schema, once.

``python -m backend.jobs.schema`` — run at deploy after Alembic (deploy.sh),
as the backend's role (bc_app owns ``jobs``). Idempotent: a no-op when the
queue table already exists, so it cannot hang or half-apply a second time.
"""

from __future__ import annotations

import asyncio
import sys

from backend.jobs.app import app


async def ensure_schema() -> bool:
    """Returns True when the schema was applied, False when it was present."""
    async with app.open_async():
        row = await app.connector.execute_query_one_async(
            "SELECT to_regclass('jobs.procrastinate_jobs') AS queue_table"
        )
        if row["queue_table"] is not None:
            return False
        await app.schema_manager.apply_schema_async()
        return True


if __name__ == "__main__":
    applied = asyncio.run(ensure_schema())
    print("procrastinate schema applied" if applied else "procrastinate schema present")
    sys.exit(0)
