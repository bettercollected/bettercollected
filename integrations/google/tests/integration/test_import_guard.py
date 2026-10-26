"""The Google Forms service refuses to start while Mongo holds 4.0 data that
Postgres lacks (googleform/db/import_guard.py, shared core:
common/db/migrate/import_guard.py).

A stack upgraded from 4.0 whose import did not finish would start without the
stored Google credentials and mirrored forms. Needs a real Mongo (``MONGO_URI``,
a scratch database) and the test Postgres; ``mongo`` marker (tests/conftest.py)."""

import dataclasses
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from bson import ObjectId
from pymongo import AsyncMongoClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from googleform.config import settings
from googleform.config.database import MongoSettings
from googleform.db.import_guard import (
    OVERRIDE_KEY,
    UnimportedMongoData,
    check_mongo_import,
    collection_tables,
)
from googleform.migrate.__main__ import build_target
from common.db.migrate import Runner

SERVICE_DIR = Path(__file__).resolve().parents[2]
MONGO_URI = os.getenv("MONGO_URI") or "mongodb://localhost:27017"
COLLECTION = "Oauth2CredentialDocument"  # the table: oauth_credentials
EMAIL = "someone.private@example.com"  # numbered per account: ``someone.private.1@...``


@pytest_asyncio.fixture
async def mongo_db():
    """A scratch Mongo database, named for the service config below."""
    name = f"google_guard_{uuid.uuid4().hex[:8]}_test"
    client = AsyncMongoClient(MONGO_URI)
    yield client[name]
    await client.drop_database(name)
    await client.close()


@pytest.fixture
def configured(monkeypatch, mongo_db):
    """The service configured as a deployment does: MONGO_URI / MONGO_DB set."""

    def configure(uri=MONGO_URI):
        monkeypatch.setenv("MONGO_DB", mongo_db.name)
        if uri is None:
            monkeypatch.delenv("MONGO_URI", raising=False)
        else:
            monkeypatch.setenv("MONGO_URI", uri)
        monkeypatch.setattr(settings, "mongo_settings", MongoSettings())

    configure()
    return configure


@pytest_asyncio.fixture
async def engine(clean_postgres):
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def no_override(monkeypatch):
    monkeypatch.delenv(OVERRIDE_KEY, raising=False)


async def insert_credentials(mongo_db, count=2):
    await mongo_db[COLLECTION].insert_many(
        [
            {
                "_id": ObjectId(),
                "email": EMAIL.replace("@", f".{i}@"),
                "user_id": f"user-{i}",
            }
            for i in range(count)
        ]
    )


def test_the_guard_covers_every_collection_the_import_migrates():
    assert set(collection_tables()) == set(build_target("postgresql://x/x_test").tables)
    assert COLLECTION in collection_tables()


def test_a_mongo_uri_held_in_the_settings_store_reaches_the_check():
    """A deployed stack keeps MONGO_URI in the settings store, not the
    environment: the guard reads it through the store-backed settings, else it
    would never see a Mongo to look into."""
    from common.settings.loader.pydantic_source import StoreBackedSettings

    assert issubclass(MongoSettings, StoreBackedSettings)


@pytest.mark.asyncio
async def test_unimported_credentials_refuse_the_start_naming_collections_and_counts(
    engine, mongo_db, configured
):
    await insert_credentials(mongo_db, 3)
    with pytest.raises(UnimportedMongoData) as refused:
        await check_mongo_import(engine)
    message = str(refused.value)
    assert f"google: {COLLECTION} (3 in Mongo, 0 in Postgres)" in message
    assert "GoogleFormDocument" not in message  # empty in Mongo
    assert "python -m googleform.migrate --group google backfill" in message
    assert OVERRIDE_KEY in message
    assert "someone.private" not in message  # counts and names only, never values
    assert MONGO_URI not in message


@pytest.mark.asyncio
async def test_an_imported_stack_starts(engine, mongo_db, configured):
    await insert_credentials(mongo_db)
    base = build_target(os.environ["DATABASE_URL"])
    target = dataclasses.replace(base, mongo_db=mongo_db.name, mongo_uri=MONGO_URI)
    async with Runner(target) as runner:
        result = await runner.backfill(None)
    assert result[COLLECTION]["state"] == "done"
    guard = await check_mongo_import(engine)
    assert guard.blocking == [] and guard.mongo_checked is False  # nothing to ask


@pytest.mark.asyncio
async def test_a_collection_emptied_after_its_import_starts(engine, mongo_db, configured):
    """A finished backfill is the import: an empty table after it is the
    application's doing, not a missing import."""
    await insert_credentials(mongo_db)
    base = build_target(os.environ["DATABASE_URL"])
    target = dataclasses.replace(base, mongo_db=mongo_db.name, mongo_uri=MONGO_URI)
    async with Runner(target) as runner:
        await runner.backfill(None)
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text('DELETE FROM "google"."oauth_credentials"'))
    assert (await check_mongo_import(engine)).blocking == []


@pytest.mark.asyncio
async def test_the_override_starts_with_a_warning(
    engine, mongo_db, configured, monkeypatch, caplog
):
    await insert_credentials(mongo_db, 2)
    monkeypatch.setenv(OVERRIDE_KEY, "google")
    with caplog.at_level(logging.WARNING):
        result = await check_mongo_import(engine)
    assert result.blocking == []
    assert [(d.collection, d.mongo) for d in result.discarded] == [(COLLECTION, 2)]
    assert f"{OVERRIDE_KEY} is set (google)" in caplog.text
    assert f"starting WITHOUT the Mongo data of google ({COLLECTION}, 2 documents)" in caplog.text
    assert "someone.private" not in caplog.text


@pytest.mark.asyncio
async def test_the_override_names_the_services_groups_only(
    engine, mongo_db, configured, monkeypatch
):
    await insert_credentials(mongo_db)
    monkeypatch.setenv(OVERRIDE_KEY, "auth")
    with pytest.raises(UnimportedMongoData, match="unknown group"):
        await check_mongo_import(engine)
    monkeypatch.setenv(OVERRIDE_KEY, "all")
    assert (await check_mongo_import(engine)).blocking == []


@pytest.mark.asyncio
async def test_without_mongo_uri_the_start_never_contacts_mongo(
    engine, mongo_db, configured
):
    await insert_credentials(mongo_db)  # data a fresh install does not have
    configured(uri=None)
    result = await check_mongo_import(engine)
    assert result.blocking == [] and result.mongo_checked is False
    configured(uri="")
    assert (await check_mongo_import(engine)).mongo_checked is False


@pytest.mark.asyncio
async def test_a_set_but_unreachable_mongo_refuses_the_start(engine, configured):
    configured(uri="mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=500")
    with pytest.raises(UnimportedMongoData) as refused:
        await check_mongo_import(engine)
    assert "MONGO_URI is set but Mongo could not be read" in str(refused.value)
    assert "127.0.0.1" not in str(refused.value)  # never the URI


PROGRAM = """
from fastapi.testclient import TestClient

from googleform.app import get_application

with TestClient(get_application()) as client:
    print("started")
"""


def boot(env: dict) -> subprocess.CompletedProcess:
    full = {k: v for k, v in os.environ.items() if k != OVERRIDE_KEY}
    full.update(env)
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=SERVICE_DIR,
        env=full,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.asyncio
async def test_the_process_refuses_to_start_then_starts_with_the_override(
    engine, mongo_db
):
    """The deployed entry point: the application factory in a fresh process."""
    await insert_credentials(mongo_db, 2)
    env = {"MONGO_URI": MONGO_URI, "MONGO_DB": mongo_db.name, "DB_AUTO_MIGRATE": "false"}
    refused = boot(env)
    assert refused.returncode != 0
    assert "UnimportedMongoData" in refused.stderr
    assert f"google: {COLLECTION} (2 in Mongo, 0 in Postgres)" in refused.stderr
    assert "started" not in refused.stdout
    assert "someone.private" not in refused.stderr

    allowed = boot({**env, OVERRIDE_KEY: "all"})
    assert allowed.returncode == 0, allowed.stderr[-3000:]
    assert "started" in allowed.stdout
