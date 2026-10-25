"""Duplicate workspace memberships: ``python -m backend.membership_duplicates``

Lists every (workspace_id, user_id) pair with more than one ``workspace_users``
membership in Postgres (``DATABASE_URL``). Ids only, never names or emails.
Read-only: it changes nothing. Exit status 1 when duplicates exist, so it can
gate a deployment. Resolve them by hand (docs/sso.md, "Duplicate
memberships"), then Postgres revision 0011 can create the unique index.

The identity group is served from Postgres only since 4.1, so Mongo is not
checked (it is listed under ``skipped``); the import from 4.0
(``python -m backend.migrate preflight``) reports duplicate memberships in a
4.0 database before they are copied.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys


async def postgres_duplicates(url: str) -> list:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT workspace_id, user_id, array_agg(id ORDER BY id) "
                    "FROM app.workspace_users GROUP BY workspace_id, user_id "
                    "HAVING count(*) > 1"
                )
            )
            return [
                {"workspace_id": w, "user_id": u, "memberships": list(ids)}
                for w, u, ids in rows
            ]
    finally:
        await engine.dispose()


def main() -> int:
    report: dict = {}
    skipped = ["mongo"]
    url = os.environ.get("DATABASE_URL")
    if url:
        report["postgres"] = asyncio.run(postgres_duplicates(url))
    else:
        skipped.append("postgres")
    print(json.dumps({**report, "skipped": skipped}, indent=2, default=str))
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
