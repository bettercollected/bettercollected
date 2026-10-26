"""``python -m auth.migrate reconcile`` honours deletion tombstones: an account
deleted in one store whose copy survives in the other is deleted there, never
copied back, in both directions.

This suite otherwise runs on an in-memory Mongo; these tests need a real one
(``MONGO_URI``, a scratch database) and the test Postgres. They carry the
``mongo`` marker (tests/conftest.py), and CI runs them with a Mongo server."""

import dataclasses
import datetime as dt
import os
import uuid

import pytest
import pytest_asyncio
from bson import ObjectId
from pymongo import AsyncMongoClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from auth.migrate.__main__ import build_target
from common.db import tombstones
from common.db.migrate import Runner

COLLECTION = "users"


@pytest_asyncio.fixture
async def target(clean_postgres):
    base = build_target(os.environ["DATABASE_URL"])
    target = dataclasses.replace(
        base, mongo_db=f"auth_tombstones_{uuid.uuid4().hex[:8]}_test"
    )
    yield target
    client = AsyncMongoClient(target.mongo_uri)
    await client.drop_database(target.mongo_db)
    await client.close()


async def record_mongo(database, collection, ids):
    """What a 4.0 Mongo delete recorded before deleting (the services no longer
    write Mongo): one tombstone document per id."""
    at = tombstones.to_ms(dt.datetime.now(dt.timezone.utc))
    await database[tombstones.COLLECTION].insert_many(
        [
            {
                "_id": f"{collection}:{i}",
                "collection": collection,
                "row_id": str(i),
                "deleted_at": at,
            }
            for i in ids
        ]
    )


async def delete_in(target, store, row_id):
    """Delete the account in one store only, with its tombstone (the other
    store's delete failed)."""
    if store == "postgres":
        table = target.tables[COLLECTION]
        engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        f'DELETE FROM "{target.schema}"."{table.name}" WHERE id = :id'
                    ),
                    {"id": row_id},
                )
                await tombstones.record_postgres(
                    conn, target.schema, COLLECTION, [row_id]
                )
        finally:
            await engine.dispose()
        return
    client = AsyncMongoClient(target.mongo_uri, tz_aware=True)
    database = client[target.mongo_db]
    await record_mongo(database, COLLECTION, [row_id])
    await database[COLLECTION].delete_one({"_id": ObjectId(row_id)})
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["mongo->postgres", "postgres->mongo"])
@pytest.mark.parametrize("deleted_in", ["postgres", "mongo"])
async def test_a_deleted_account_is_never_copied_back(target, direction, deleted_in):
    written = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    kept, gone = ObjectId(), ObjectId()
    client = AsyncMongoClient(target.mongo_uri, tz_aware=True)
    users = client[target.mongo_db][COLLECTION]
    await users.insert_many(
        [
            {"_id": kept, "email": f"{kept}@example.com", "updated_at": written},
            {"_id": gone, "email": f"{gone}@example.com", "updated_at": written},
        ]
    )
    async with Runner(target) as runner:
        await runner.backfill([COLLECTION])
    await delete_in(target, deleted_in, str(gone))

    async with Runner(target) as runner:
        (before,) = await runner.verify([COLLECTION])
        result = await runner.reconcile([COLLECTION], direction=direction)
        (after,) = await runner.verify([COLLECTION])
    assert before.tombstoned == 1
    assert result[COLLECTION]["deleted"] == 1
    assert after.clean and after.mongo == after.postgres == 1
    assert await users.find_one({"_id": gone}) is None
    await client.close()
