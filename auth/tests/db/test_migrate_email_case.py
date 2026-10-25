"""``python -m auth.migrate preflight`` reports accounts whose emails differ
only in case before a backfill would stop on them (``uq_users_email_lower``),
and the backfill never merges them.

Needs a real Mongo (``MONGO_URI``, a scratch database) and the test Postgres;
``mongo`` marker (tests/conftest.py)."""

import dataclasses
import os
import uuid

import pytest
import pytest_asyncio
from bson import ObjectId
from pymongo import AsyncMongoClient

from auth.migrate.__main__ import build_target
from common.db.migrate import Runner

COLLECTION = "users"


@pytest_asyncio.fixture
async def target(clean_postgres):
    base = build_target(os.environ["DATABASE_URL"])
    target = dataclasses.replace(
        base, mongo_db=f"auth_email_case_{uuid.uuid4().hex[:8]}_test"
    )
    yield target
    client = AsyncMongoClient(target.mongo_uri)
    await client.drop_database(target.mongo_db)
    await client.close()


@pytest.mark.asyncio
async def test_preflight_counts_case_variants_and_backfill_merges_none(target):
    client = AsyncMongoClient(target.mongo_uri)
    users = client[target.mongo_db][COLLECTION]
    await users.insert_many(
        [
            {"_id": ObjectId(), "email": "Jane@Example.com"},
            {"_id": ObjectId(), "email": "jane@example.com"},
            {"_id": ObjectId(), "email": "other@example.com"},
            {"_id": ObjectId()},  # no email: never a duplicate
            {"_id": ObjectId()},
        ]
    )
    async with Runner(target) as runner:
        (report,) = await runner.preflight([COLLECTION])
        assert report.duplicates == 1
        result = await runner.backfill([COLLECTION])
    # the unique index stops the collection; nothing is merged or dropped
    assert result[COLLECTION]["state"] == "error"
    assert "uq_users_email_lower" in result[COLLECTION]["error"]
    assert await users.count_documents({}) == 5

    await users.delete_one({"email": "jane@example.com"})
    async with Runner(target) as runner:
        (report,) = await runner.preflight([COLLECTION])
        assert report.duplicates == 0
        result = await runner.backfill([COLLECTION], restart=True)
    assert result[COLLECTION]["state"] == "done"
    await client.close()


@pytest.mark.asyncio
async def test_preflight_reports_counts_only_and_fails(target, caplog, capsys):
    """Distinct lower-cased emails held by more than one account, and the
    accounts involved; never an email or an id. A blocker: exit 1."""
    import asyncio
    import logging

    from common.db.migrate.cli import main

    client = AsyncMongoClient(target.mongo_uri)
    ids = [ObjectId() for _ in range(7)]
    emails = [
        "ann@example.com",
        "Ann@Example.com",
        "ANN@EXAMPLE.COM",
        "bob@example.com",
        "Bob@example.com",
        "carol@example.com",
        "",
    ]
    await client[target.mongo_db][COLLECTION].insert_many(
        [{"_id": i, "email": e} for i, e in zip(ids, emails)]
    )
    await client.close()
    caplog.set_level(logging.WARNING)
    async with Runner(target) as runner:
        (report,) = await runner.preflight([COLLECTION])
    assert (report.case_variant_keys, report.case_variant_documents) == (2, 5)
    assert report.duplicates == 2
    warning = caplog.text
    assert "2 values are held by 5 documents" in warning
    assert "example.com" not in warning.lower()
    assert not any(str(i) in warning for i in ids)

    code = await asyncio.to_thread(
        main, ["preflight"], target, prog="python -m auth.migrate", env={}
    )
    out = capsys.readouterr().out
    assert code == 1
    assert '"case_variant_keys": 2' in out
    assert '"case_variant_documents": 5' in out
    assert "example.com" not in out.lower()
    assert not any(str(i) in out for i in ids)
