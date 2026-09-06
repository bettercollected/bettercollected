import os
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from common.db import (
    BaseRow,
    DatabaseSettings,
    canonical_document,
    document_checksum,
    make_base,
    make_engine,
    make_sessionmaker,
    ping,
)
from common.db.base import SOURCE_BACKFILL

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)

SCHEMA = "common_test"
Base = make_base(SCHEMA)


class Probe(Base, BaseRow):
    __tablename__ = "probe"


@pytest.fixture
async def engine():
    engine = make_engine(DatabaseSettings.from_env(), application_name="common-tests")
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    await engine.dispose()


async def test_ping_and_the_session_timeouts_are_applied_server_side(engine):
    assert await ping(engine)
    async with engine.connect() as conn:
        show = lambda name: conn.execute(text(f"SHOW {name}"))
        assert (await show("statement_timeout")).scalar_one() == "30s"
        assert (await show("lock_timeout")).scalar_one() == "5s"
        assert (
            await show("idle_in_transaction_session_timeout")
        ).scalar_one() == "1min"
        assert (await show("application_name")).scalar_one() == "common-tests"


async def test_insert_stamps_source_checksum_and_timestamps(engine):
    Session = make_sessionmaker(engine)
    mongo_doc = {"_id": ObjectId(), "workspace_id": ObjectId(), "title": "t"}
    async with Session() as session:
        session.add(Probe(id=str(mongo_doc["_id"]), doc=canonical_document(mongo_doc)))
        await session.commit()
    async with Session() as session:
        row = await session.get(Probe, str(mongo_doc["_id"]))
    assert row.bc_source == "app"
    assert row.bc_checksum == document_checksum(mongo_doc)
    assert row.created_at is not None and row.updated_at is not None
    assert row.doc["_id"] == {"$oid": row.id}


async def test_update_bumps_updated_at_and_recomputes_the_checksum(engine):
    Session = make_sessionmaker(engine)
    oid = str(ObjectId())
    async with Session() as session:
        session.add(Probe(id=oid, doc={"_id": {"$oid": oid}, "title": "before"}))
        await session.commit()
        row = await session.get(Probe, oid)
        first_checksum, first_updated = row.bc_checksum, row.updated_at
        row.doc = {**row.doc, "title": "after"}
        await session.commit()
        await session.refresh(row)
    assert row.bc_checksum != first_checksum
    assert row.updated_at > first_updated


async def test_backfilled_rows_keep_the_timestamps_copied_from_mongo(engine):
    Session = make_sessionmaker(engine)
    oid = str(ObjectId())
    then = datetime(2020, 1, 1, tzinfo=timezone.utc)
    async with Session() as session:
        session.add(
            Probe(
                id=oid,
                doc={"_id": {"$oid": oid}},
                bc_source=SOURCE_BACKFILL,
                created_at=then,
                updated_at=then,
            )
        )
        await session.commit()
        row = await session.get(Probe, oid)
        assert (row.created_at, row.updated_at) == (then, then)
        assert row.bc_checksum
        row.doc = {**row.doc, "touched": True}
        await session.commit()
        await session.refresh(row)
    assert row.updated_at == then  # a backfilled row is never re-stamped


async def test_id_must_be_a_24_hex_object_id(engine):
    Session = make_sessionmaker(engine)
    async with Session() as session:
        session.add(Probe(id="not-an-object-id", doc={}))
        with pytest.raises(IntegrityError, match="id_is_object_id"):
            await session.commit()
