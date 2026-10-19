"""``python -m googleform.migrate``: one group, and a clean verify writes the
"migration verified" marker into the google schema. Real Mongo (a scratch
database) and the test Postgres; skipped without a *_test DATABASE_URL."""

import dataclasses
import os
import uuid

import pytest
import pytest_asyncio
from bson import ObjectId
from pymongo import AsyncMongoClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from common.db.marker import migration_verified
from common.db.migrate import Runner
from common.db.migrate.cli import main
from googleform.migrate.__main__ import _tables, build_target


@pytest_asyncio.fixture
async def target(clean_postgres):
    base = build_target(os.environ["DATABASE_URL"])
    target = dataclasses.replace(
        base, mongo_db=f"{base.mongo_db}_migrate_{uuid.uuid4().hex[:8]}"
    )
    yield target
    client = AsyncMongoClient(target.mongo_uri)
    await client.drop_database(target.mongo_db)
    await client.close()


def test_every_collection_is_in_the_google_group():
    target = build_target("postgresql+asyncpg://unused/unused_test")
    assert target.service == "google" and target.group_names() == ["google"]
    assert set(target.groups) == set(_tables())
    assert target.marker is not None and target.marker.name == "store_migration"
    assert "+schema.0003" in target.code_version


def test_an_unknown_group_is_refused(capsys):
    target = build_target("postgresql+asyncpg://unused/unused_test")
    with pytest.raises(SystemExit) as exit_:
        main(
            ["--group", "forms", "verify"], target, prog="python -m googleform.migrate"
        )
    assert exit_.value.code == 2
    assert "valid groups: google" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_a_clean_verify_writes_the_marker(target):
    client = AsyncMongoClient(target.mongo_uri)
    collection = next(iter(target.tables))
    await client[target.mongo_db][collection].insert_one(
        {"_id": ObjectId(), "state": "x"}
    )
    await client.close()
    async with Runner(target) as runner:
        await runner.backfill()
        outcome = await runner.record_verify(await runner.verify())
    assert outcome["marker"] == "written" and outcome["groups"] == ["google"]
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            marker = await migration_verified(conn, "google")
    finally:
        await engine.dispose()
    assert marker is not None and marker.groups == ("google",)
    assert marker.counts()[collection] == {"mongo": 1, "postgres": 1}
