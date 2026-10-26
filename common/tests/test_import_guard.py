"""The shared startup guard against unimported Mongo data
(common/db/migrate/import_guard.py): what it asks, when it refuses, and what it
says. Services supply their own collections; here a made-up one with two groups.

Mongo is a stand-in that counts what it is asked (or a real client on a closed
port for the unreachable case); the Postgres probe runs on a live Postgres."""

import logging
import os

import pytest
from sqlalchemy import text

from common.db import DatabaseSettings, make_base, make_engine
from common.db.base import BaseRow
from common.db.migrate import MigrationProgressMixin
from common.db.migrate import import_guard as guard
from common.db.migrate.import_guard import (
    OVERRIDE_KEY,
    PostgresState,
    UnimportedMongoData,
    check_unimported_mongo_data,
    collection_tables,
    mongo_uri_configured,
    override_groups,
)

SCHEMA = "common_guard_test"
Base = make_base(SCHEMA)
DB = "guard_db"
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=500"
COLLECTIONS = {"Accounts": "people", "Notes": "people", "Things": "stuff"}
GROUPS = ("people", "stuff")


class Account(Base, BaseRow):
    __tablename__ = "accounts"
    __mongo_collection__ = "Accounts"


class Note(Base, BaseRow):
    __tablename__ = "notes"
    __mongo_collection__ = "Notes"


class Thing(Base, BaseRow):
    __tablename__ = "things"
    __mongo_collection__ = "Things"


class Progress(Base, MigrationProgressMixin):
    __tablename__ = "migration_progress"


class FakeCollection:
    def __init__(self, database, name):
        self.database, self.name = database, name

    async def find_one(self, *args, **kwargs):
        self.database.asked.append(self.name)
        return {"_id": 1} if self.database.counts.get(self.name) else None

    async def estimated_document_count(self):
        return self.database.counts.get(self.name, 0)


class FakeDatabase:
    def __init__(self, counts):
        self.counts, self.asked = counts, []

    def __getitem__(self, name):
        return FakeCollection(self, name)


def fake_client(counts=None):
    database = FakeDatabase(counts or {})
    return {DB: database}, database


async def check(client=None, uri="", env=None, state=None, groups=GROUPS, **kwargs):
    return await check_unimported_mongo_data(
        None,  # the Postgres side is given as ``state`` unless a test probes it
        collections=COLLECTIONS,
        migrate_module="demo.migrate",
        client=client,
        uri=uri,
        database=DB,
        groups=groups,
        env=env or {},
        state=state if state is not None else PostgresState(),
        **kwargs,
    )


# -- the collection map -----------------------------------------------------
def test_collection_tables_maps_every_importable_row():
    tables = collection_tables(Base)
    assert set(tables) == {"Accounts", "Notes", "Things"}
    assert tables["Accounts"].name == "accounts"  # not the checkpoint table


# -- the decision -------------------------------------------------------------
async def test_unimported_rows_refuse_naming_groups_collections_and_counts():
    client, _ = fake_client({"Accounts": 3, "Things": 1})
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client)
    message = str(refused.value)
    assert "people: Accounts (3 in Mongo, 0 in Postgres)" in message
    assert "stuff: Things (1 in Mongo, 0 in Postgres)" in message
    assert "Notes" not in message  # empty in Mongo
    assert "`python -m demo.migrate --group people,stuff backfill`" in message
    assert "`python -m demo.migrate status`" in message
    assert f"{OVERRIDE_KEY}=people,stuff" in message


async def test_rows_in_postgres_and_finished_imports_are_not_asked_about():
    client, database = fake_client({"Accounts": 3, "Notes": 3, "Things": 3})
    result = await check(
        client,
        state=PostgresState(
            has_rows=frozenset({"Accounts"}), imported=frozenset({"Notes", "Things"})
        ),
    )
    assert result.blocking == [] and not result.mongo_checked
    assert database.asked == []


async def test_an_empty_mongo_starts():
    client, database = fake_client({})
    result = await check(client)
    assert result.mongo_checked and result.blocking == []
    assert sorted(database.asked) == ["Accounts", "Notes", "Things"]


async def test_without_mongo_uri_mongo_is_never_contacted(monkeypatch):
    def no_client(*args, **kwargs):
        raise AssertionError("Mongo contacted")

    monkeypatch.setattr(guard, "AsyncMongoClient", no_client)
    result = await check(client=None, uri="")
    assert not result.mongo_checked and result.blocking == []


async def test_a_configured_but_unreachable_mongo_refuses_without_the_uri():
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client=None, uri=UNREACHABLE)
    message = str(refused.value)
    assert "MONGO_URI is set but Mongo could not be read" in message
    assert "people, stuff" in message
    assert "127.0.0.1" not in message  # never the URI (it may hold a password)


async def test_an_unreachable_mongo_is_not_asked_when_nothing_is_missing():
    result = await check(
        uri=UNREACHABLE,
        state=PostgresState(has_rows=frozenset(COLLECTIONS)),
    )
    assert not result.mongo_checked


# -- the override -------------------------------------------------------------
@pytest.mark.parametrize("value", ["all", "people,stuff", " People , STUFF "])
async def test_the_override_starts_with_a_warning_per_collection(value, caplog):
    client, _ = fake_client({"Accounts": 2, "Things": 5})
    with caplog.at_level(logging.WARNING):
        result = await check(client, env={OVERRIDE_KEY: value})
    assert result.blocking == []
    assert [(d.collection, d.mongo) for d in result.discarded] == [
        ("Accounts", 2),
        ("Things", 5),
    ]
    assert f"{OVERRIDE_KEY} is set (people, stuff)" in caplog.text
    assert "WITHOUT the Mongo data of people (Accounts, 2 documents)" in caplog.text
    assert "WITHOUT the Mongo data of stuff (Things, 5 documents)" in caplog.text


async def test_the_override_covers_only_the_groups_it_names():
    client, _ = fake_client({"Accounts": 2, "Things": 5})
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client, env={OVERRIDE_KEY: "stuff"})
    message = str(refused.value)
    assert "people: Accounts (2 in Mongo" in message
    assert "Things" not in message
    assert "--group people backfill" in message


async def test_the_override_is_silent_when_nothing_is_missing(caplog):
    client, _ = fake_client({})
    with caplog.at_level(logging.WARNING):
        await check(client, env={OVERRIDE_KEY: "all"})
    assert "WITHOUT" not in caplog.text


@pytest.mark.parametrize("value", ["nonsense", "people,nonsense", "true", "auth"])
async def test_an_override_naming_an_unknown_group_refuses(value):
    with pytest.raises(UnimportedMongoData, match="unknown group"):
        await check(fake_client({})[0], env={OVERRIDE_KEY: value})


def test_override_groups_reads_all_a_list_or_nothing():
    assert override_groups({}, GROUPS) == frozenset()
    assert override_groups({OVERRIDE_KEY: "  "}, GROUPS) == frozenset()
    assert override_groups({OVERRIDE_KEY: "ALL"}, GROUPS) == frozenset(GROUPS)
    assert override_groups({OVERRIDE_KEY: "stuff"}, GROUPS) == {"stuff"}


# -- MONGO_URI as configured --------------------------------------------------
def test_only_a_configured_mongo_uri_counts_not_the_default():
    from pydantic import BaseModel

    class Mongo(BaseModel):
        URI: str = "mongodb://localhost"

    assert mongo_uri_configured(Mongo()) == ""
    assert mongo_uri_configured(Mongo(URI=" mongodb://db ")) == "mongodb://db"
    assert mongo_uri_configured(Mongo(URI="")) == ""


async def test_state_is_needed_unless_tables_are_given():
    with pytest.raises(ValueError):
        await check_unimported_mongo_data(
            None,
            collections=COLLECTIONS,
            migrate_module="demo.migrate",
            client=None,
            uri="",
            database=DB,
            groups=GROUPS,
        )


# -- the Postgres probe (live) ------------------------------------------------
pg = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)


@pytest.fixture
async def engine():
    engine = make_engine(DatabaseSettings.from_env(), application_name="guard-tests")
    async with engine.begin() as c:
        await c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await c.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        await c.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as c:
        await c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    await engine.dispose()


@pg
async def test_the_probe_finds_rows_and_finished_backfills(engine):
    tables = collection_tables(Base)
    async with engine.begin() as conn:
        await conn.execute(
            Account.__table__.insert(),
            [{"id": "0123456789abcdef01234567", "doc": {}, "_bc_source": "app", "_bc_checksum": "x"}],
        )
        await conn.execute(
            Progress.__table__.insert(),
            [
                {"collection": "Notes", "state": "done", "count": 0},
                {"collection": "Things", "state": "paused", "count": 0},
            ],
        )
    state = await guard.postgres_state(engine, tables, Progress.__table__)
    assert state.has_rows == {"Accounts"}
    assert state.imported == {"Notes"}


@pg
async def test_probing_end_to_end_lets_through_what_postgres_has(engine):
    async with engine.begin() as conn:
        await conn.execute(
            Account.__table__.insert(),
            [{"id": "0123456789abcdef01234567", "doc": {}, "_bc_source": "app", "_bc_checksum": "x"}],
        )
    client, _ = fake_client({"Accounts": 1, "Notes": 4, "Things": 1})
    kwargs = dict(
        collections=COLLECTIONS,
        tables=collection_tables(Base),
        progress=Progress.__table__,
        migrate_module="demo.migrate",
        client=client,
        uri="",
        database=DB,
        groups=GROUPS,
        env={},
    )
    with pytest.raises(UnimportedMongoData) as refused:
        await check_unimported_mongo_data(engine, **kwargs)
    message = str(refused.value)
    assert "people: Notes (4 in Mongo, 0 in Postgres)" in message
    assert "stuff: Things (1 in Mongo, 0 in Postgres)" in message
    assert "Accounts" not in message
