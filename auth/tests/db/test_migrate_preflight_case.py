"""``python -m auth.migrate preflight`` counts the accounts whose emails differ
only in letter case: a later release makes an email unique ignoring case. A
warning with counts only (never an email or an id); preflight still passes,
because such accounts keep working on this release.

Needs a real Mongo (``MONGO_URI``, a scratch database) and the test Postgres;
the ``mongo`` marker (tests/conftest.py) runs it in CI's job with Mongo."""

import dataclasses
import logging
import os
import uuid

import pytest
import pytest_asyncio
from bson import ObjectId
from pymongo import AsyncMongoClient

from auth.migrate.__main__ import build_target
from common.db.migrate import Runner
from common.db.migrate.cli import main


@pytest_asyncio.fixture
async def target(clean_postgres):
    base = build_target(os.environ["DATABASE_URL"])
    target = dataclasses.replace(
        base, mongo_db=f"auth_preflight_{uuid.uuid4().hex[:8]}_test"
    )
    yield target
    client = AsyncMongoClient(target.mongo_uri)
    await client.drop_database(target.mongo_db)
    await client.close()


async def users(target, emails):
    client = AsyncMongoClient(target.mongo_uri)
    await client[target.mongo_db]["users"].insert_many(
        [{"_id": ObjectId(), "email": e} for e in emails]
    )
    await client.close()


@pytest.mark.asyncio
async def test_preflight_counts_case_variant_emails_as_a_warning(target, caplog):
    await users(
        target,
        [
            "ann@example.com",
            "Ann@Example.com",
            "ANN@EXAMPLE.COM",
            "bob@example.com",
            "Bob@example.com",
            "carol@example.com",
            "",
        ],
    )
    caplog.set_level(logging.WARNING)
    async with Runner(target) as runner:
        (report,) = await runner.preflight(["users"])
    assert report.case_variant_keys == 2
    assert report.case_variant_documents == 5
    assert report.duplicates == 0  # exact duplicates only: none
    warning = "\n".join(r.getMessage() for r in caplog.records)
    assert "2 values are held by 5 documents" in warning
    assert "example.com" not in warning


@pytest.mark.asyncio
async def test_case_variants_do_not_fail_preflight(target, capsys):
    import asyncio

    await users(target, ["dee@example.com", "Dee@example.com"])
    code = await asyncio.to_thread(
        main,
        ["preflight"],
        target,
        prog="python -m auth.migrate",
        env={"DB_WRITE_MODE": "dual"},
    )
    out = capsys.readouterr().out
    assert code == 0
    assert '"case_variant_keys": 1' in out
    assert '"case_variant_documents": 2' in out
    assert "example.com" not in out


@pytest.mark.asyncio
async def test_no_case_variants_no_warning(target, caplog):
    await users(target, ["eve@example.com", "frank@example.com"])
    caplog.set_level(logging.WARNING)
    async with Runner(target) as runner:
        (report,) = await runner.preflight(["users"])
    assert (report.case_variant_keys, report.case_variant_documents) == (0, 0)
    assert "letter case" not in caplog.text
