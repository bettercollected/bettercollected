"""The start refuses while a Postgres-only group's data is in Mongo but was never
imported into Postgres (backend/db/mongo_import_guard.py).

Postgres is this worker's test database (empty at each test); Mongo is a stand-in
that counts what it is asked, or a real client on a closed port for the
unreachable case, so these run without a Mongo server.
"""

import pytest
from loguru import logger
from sqlalchemy import insert

from backend.app.container import container
from backend.db import mongo_import_guard as guard
from backend.db.groups import COLLECTION_GROUPS, POSTGRES_ONLY_GROUPS
from backend.db.models import MigrationProgress
from backend.db.mongo_import_guard import (
    OVERRIDE_KEY,
    PostgresState,
    UnimportedMongoData,
    check_unimported_mongo_data,
    guarded_collections,
)
from tests.app.db.beanie_originals import PostgresAllowedOriginsRepository
from tests.conftest import _postgres_configured

pytestmark = pytest.mark.skipif(
    not _postgres_configured(), reason="DATABASE_URL not set to a *_test database"
)

DB = "guard_test"
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=500"


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


def collections_of(group):
    return [c for c, g in COLLECTION_GROUPS.items() if g == group]


async def check(client=None, uri="", env=None, state=None, groups=POSTGRES_ONLY_GROUPS):
    return await check_unimported_mongo_data(
        container.pg_engine(),
        client=client,
        uri=uri,
        database=DB,
        env=env or {},
        state=state,
        groups=groups,
    )


@pytest.fixture
def warnings():
    found = []
    handler = logger.add(lambda m: found.append(str(m)), level="WARNING")
    yield found
    logger.remove(handler)


def test_the_guard_covers_exactly_the_postgres_only_groups_collections():
    assert set(guarded_collections().values()) == set(POSTGRES_ONLY_GROUPS)
    assert set(guarded_collections()) == {
        c for c, g in COLLECTION_GROUPS.items() if g in POSTGRES_ONLY_GROUPS
    }
    assert "allowed_origins" in guarded_collections()
    assert "workspaces" in guarded_collections()
    assert "forms" in guarded_collections()
    assert "form_responses" in guarded_collections()
    assert "workspace_tags" in guarded_collections()


# -- per group --------------------------------------------------------------
@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_mongo_rows_and_an_empty_postgres_refuse_the_start(group):
    names = collections_of(group)
    client, database = fake_client({n: 3 for n in names})
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client)
    message = str(refused.value)
    assert f"the {group} group(s) are served from Postgres only" in message
    for name in names:
        assert f"{group}: {name} (3 in Mongo, 0 in Postgres)" in message
    assert f"python -m backend.migrate --group {group} backfill" in message
    assert OVERRIDE_KEY in message
    for other in set(POSTGRES_ONLY_GROUPS) - {group}:
        assert f"{other}:" not in message


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_data_in_both_stores_starts(group):
    names = collections_of(group)
    client, database = fake_client({n: 3 for n in names})
    result = await check(client, state=PostgresState(has_rows=frozenset(names)))
    assert result.blocking == [] and result.discarded == []
    assert not set(database.asked) & set(names)  # Postgres has rows: not asked


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_an_imported_collection_emptied_since_starts(group):
    """A finished backfill is the import: an empty table after it is the
    application's doing (rows deleted or expired), not missing data."""
    names = collections_of(group)
    client, database = fake_client({n: 3 for n in names})
    result = await check(client, state=PostgresState(imported=frozenset(names)))
    assert result.blocking == []
    assert not set(database.asked) & set(names)


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_an_empty_mongo_starts(group):
    client, database = fake_client({})
    result = await check(client, groups=(group,))
    assert result.mongo_checked and result.blocking == []
    assert sorted(database.asked) == sorted(collections_of(group))


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_without_mongo_uri_the_start_never_contacts_mongo(group, monkeypatch):
    def no_client(*args, **kwargs):
        raise AssertionError("Mongo contacted")

    monkeypatch.setattr(guard, "AsyncMongoClient", no_client)
    result = await check(client=None, uri="", groups=(group,))
    assert not result.mongo_checked and result.blocking == []


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_an_unreachable_configured_mongo_refuses_the_start(group):
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client=None, uri=UNREACHABLE, groups=(group,))
    message = str(refused.value)
    assert "MONGO_URI is set but Mongo could not be read" in message
    assert group in message
    assert "127.0.0.1" not in message  # never the URI (it may hold a password)


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
@pytest.mark.parametrize("value", ["all", "{group}", "ai,{group}"])
async def test_the_override_starts_with_a_warning(group, value, warnings):
    names = collections_of(group)
    client, _ = fake_client({n: 2 for n in names})
    result = await check(client, env={OVERRIDE_KEY: value.format(group=group)})
    assert result.blocking == []
    assert [d.collection for d in result.discarded] == names
    text = "\n".join(warnings)
    assert f"{OVERRIDE_KEY} is set" in text
    for name in names:
        assert (
            f"starting WITHOUT the Mongo data of {group} ({name}, 2 documents)" in text
        )


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
async def test_the_override_covers_only_the_groups_it_names(group):
    other = next(g for g in POSTGRES_ONLY_GROUPS if g != group)
    client, _ = fake_client(
        {n: 1 for n in collections_of(group) + collections_of(other)}
    )
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client, env={OVERRIDE_KEY: other})
    message = str(refused.value)
    assert f"--group {group} backfill" in message
    assert f"{other}:" not in message


# -- the override's value and the Postgres probe ----------------------------
async def test_an_override_naming_an_unknown_group_refuses():
    client, _ = fake_client({})
    with pytest.raises(UnimportedMongoData, match="unknown group"):
        await check(client, env={OVERRIDE_KEY: "refdata,nonsense"})
    with pytest.raises(UnimportedMongoData, match="unknown group"):
        await check(client, env={OVERRIDE_KEY: "true"})


async def test_the_postgres_probe_finds_rows_and_finished_backfills():
    await PostgresAllowedOriginsRepository(container.pg_sessionmaker()).add(
        "https://a.example"
    )
    async with container.pg_engine().begin() as conn:
        await conn.execute(
            insert(MigrationProgress.__table__),
            [
                {"collection": "coupon_codes", "state": "done", "count": 0},
                {"collection": "user_feedback", "state": "paused", "count": 0},
            ],
        )
    tables = guard.collection_tables()
    state = await guard.postgres_state(
        container.pg_engine(),
        {c: tables[c] for c in guarded_collections()},
        MigrationProgress.__table__,
    )
    assert state.has_rows == {"allowed_origins"}
    assert state.imported == {"coupon_codes"}
    # end to end: the probed state lets those two through, a paused backfill does not
    client, _ = fake_client(
        {"allowed_origins": 1, "coupon_codes": 1, "user_feedback": 1}
    )
    with pytest.raises(UnimportedMongoData) as refused:
        await check(client)
    message = str(refused.value)
    assert "refdata: user_feedback (1 in Mongo, 0 in Postgres)" in message
    assert "allowed_origins" not in message and "coupon_codes" not in message
