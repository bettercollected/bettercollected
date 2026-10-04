"""Duplicate workspace memberships: ``python -m backend.membership_duplicates``

Lists every (workspace_id, user_id) pair with more than one ``workspace_users``
membership, in Mongo (``MONGO_DB``) and, when ``DATABASE_URL`` is set, in the
Postgres twin. Ids, roles and the disabled flag only, never names or emails.
Read-only: it changes nothing. Exit status 1 when duplicates exist, so it can
gate a deployment. Resolve them by hand (docs/sso.md, "Duplicate
memberships"), then the unique index (Mongo at startup, Postgres revision
0011) can be created.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from pymongo import MongoClient

from backend.config import settings


def mongo_duplicates() -> list:
    client = MongoClient(settings.mongo_settings.URI)
    try:
        rows = client[settings.mongo_settings.DB]["workspace_users"].aggregate(
            [
                {
                    "$group": {
                        "_id": {"w": "$workspace_id", "u": "$user_id"},
                        "n": {"$sum": 1},
                        "memberships": {
                            "$push": {
                                "id": {"$toString": "$_id"},
                                "roles": "$roles",
                                "disabled": "$disabled",
                            }
                        },
                    }
                },
                {"$match": {"n": {"$gt": 1}}},
            ]
        )
        return [
            {
                "workspace_id": str(row["_id"]["w"]),
                "user_id": str(row["_id"]["u"]),
                "memberships": row["memberships"],
            }
            for row in rows
        ]
    finally:
        client.close()


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
    report = {"mongo": mongo_duplicates()}
    url = os.environ.get("DATABASE_URL")
    if url:
        report["postgres"] = asyncio.run(postgres_duplicates(url))
    print(json.dumps(report, indent=2, default=str))
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
