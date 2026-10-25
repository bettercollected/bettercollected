"""``python -m backend.migrate resolve-outbox``: resolve the Postgres-side
outbox entries whose write Mongo holds, after a group was rolled back from
``postgres_primary_dual`` to ``dual`` (the runbook's "stuck case").

Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import contextlib
import datetime as dt
import io
import json
import os
import stat

import pytest
from beanie import PydanticObjectId
from dependency_injector import providers
from pymongo import AsyncMongoClient
from sqlalchemy import select

from backend.app.container import AppContainer, container
from backend.db.models import DeletionTombstone, MirrorWriteFailure, SessionRow
from backend.migrate.__main__ import build_target, repository_groups
from common.db import RoutingRepository
from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum
from common.db.migrate import Runner
from common.db.migrate.cli import main

UTC = dt.timezone.utc
PAST = dt.datetime.now(UTC).replace(microsecond=0) - dt.timedelta(hours=1)


@pytest.fixture
def target(clean_postgres):
    return build_target(os.environ["DATABASE_URL"])


@contextlib.asynccontextmanager
async def mongo(target):
    client = AsyncMongoClient(target.mongo_uri, tz_aware=True)
    try:
        yield client[target.mongo_db]
    finally:
        await client.close()


def session_document(**changes):
    return {
        "_id": PydanticObjectId(),
        "user_id": "u1",
        "refresh_jti": "jti",
        "last_refreshed_at": PAST,
        "expires_at": PAST + dt.timedelta(days=7),
        "email_verified": True,
        "user_agent": None,
        "revoked_at": None,
        "created_at": PAST,
        "updated_at": PAST,
        **changes,
    }


async def to_mongo(target, document):
    async with mongo(target) as db:
        await db["sessions"].replace_one(
            {"_id": document["_id"]}, document, upsert=True
        )


async def to_postgres(document, *, updated_at=PAST):
    doc = canonical_document(document)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            SessionRow(
                id=str(document["_id"]),
                doc=doc,
                created_at=PAST,
                updated_at=updated_at,
                bc_source=SOURCE_APP,
                bc_checksum=checksum(doc),
            )
        )


async def open_entry(row_id, repository="SessionRepository"):
    """A Postgres-side entry, recorded now (the database's clock)."""
    async with container.pg_sessionmaker()() as session, session.begin():
        entry = MirrorWriteFailure(
            table_name=repository,
            row_id=row_id,
            op="update",
            error="ConnectionError: store unreachable",
        )
        session.add(entry)
    return entry.id


async def open_ids():
    async with container.pg_sessionmaker()() as session:
        rows = await session.execute(
            select(MirrorWriteFailure.id).where(
                MirrorWriteFailure.resolved_at.is_(None)
            )
        )
        return sorted(r[0] for r in rows.all())


def later():
    """A time after every entry recorded so far (Mongo keeps milliseconds)."""
    return dt.datetime.now(UTC).replace(microsecond=0) + dt.timedelta(minutes=1)


async def cli(target, *argv, env=None):
    """``python -m backend.migrate <argv>``: (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = await asyncio.to_thread(
            main, list(argv), target, prog="python -m backend.migrate", env=env or {}
        )
    return code, out.getvalue()


async def resolve(target, *argv):
    code, out = await cli(target, "resolve-outbox", *argv)
    return code, json.loads(out)


async def resolve_group(target, group, *argv):
    code, out = await cli(target, "--group", group, "resolve-outbox", *argv)
    return code, json.loads(out)


# -- the repository map -----------------------------------------------------------
def test_every_routed_repository_has_its_group():
    groups = repository_groups()
    checked = 0
    for provider in AppContainer.providers.values():
        if not isinstance(provider, providers.Singleton):
            continue
        if provider.provides is not RoutingRepository:
            continue
        mongo_impl = provider.kwargs.get("mongo")
        assert mongo_impl is not None
        assert groups[mongo_impl.provides.__name__] == provider.kwargs["group"]
        checked += 1
    assert checked > 30
    assert groups["SessionRepository"] == "identity"


# -- resolving ----------------------------------------------------------------------
async def test_entries_whose_writes_are_in_mongo_are_resolved(target):
    same = session_document(user_agent="same in both")
    await to_mongo(target, same)
    await to_postgres(same)
    # written in Postgres, then overwritten in Mongo by a later write
    overtaken = session_document(user_agent="the Postgres write")
    await to_postgres(overtaken)
    await open_entry(f"{same['_id']},jti")
    await open_entry(str(overtaken["_id"]))
    await open_entry("-")  # names nothing: the group's rows decide
    await to_mongo(
        target,
        {**overtaken, "user_agent": "a later Mongo write", "updated_at": later()},
    )
    code, result = await resolve(target, "--apply")
    assert code == 0, result
    assert (result["in_scope"], result["resolvable"], result["resolved"]) == (3, 3, 3)
    assert result["groups"]["identity"]["rows_differing"] == 0
    assert await open_ids() == []


async def test_entries_whose_writes_are_missing_stay_open(target):
    only_postgres = session_document(user_agent="never reached Mongo")
    await to_postgres(only_postgres)
    newer_in_postgres = session_document()
    await to_mongo(target, newer_in_postgres)
    await to_postgres(
        {**newer_in_postgres, "user_agent": "the Postgres write"},
        updated_at=PAST + dt.timedelta(minutes=5),
    )
    missing = await open_entry(str(only_postgres["_id"]))
    older = await open_entry(str(newer_in_postgres["_id"]))
    unnamed = await open_entry("-")
    other_group = await open_entry("-", repository="AllowedOriginsRepository")
    unknown = await open_entry("-", repository="NoSuchRepository")
    code, result = await resolve(target, "--apply")
    assert code == 1
    assert result["kept"] == {
        "unknown_repository": 1,
        "missing_in_mongo": 1,
        "older_in_mongo": 1,
        "delete_pending": 0,
        "group_differs": 1,
    }
    assert result["groups"]["identity"]["rows_differing"] == 2
    assert result["resolved"] == 1  # the refdata entry: nothing differs there
    assert await open_ids() == sorted([missing, older, unnamed, unknown])
    assert other_group not in await open_ids()


async def test_a_mongo_copy_older_than_a_delete_keeps_the_entry(target):
    deleted = session_document()
    await to_mongo(target, deleted)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            DeletionTombstone(
                collection="sessions",
                row_id=str(deleted["_id"]),
                deleted_at=PAST + dt.timedelta(minutes=1),
            )
        )
    await open_entry(str(deleted["_id"]))
    code, result = await resolve(target)
    assert code == 1
    assert result["kept"]["delete_pending"] == 1


async def test_the_dry_run_changes_nothing_and_ids_go_only_to_the_file(
    target, tmp_path
):
    document = session_document(user_agent="same in both")
    await to_mongo(target, document)
    await to_postgres(document)
    entry = await open_entry(str(document["_id"]))
    ids_file = tmp_path / "outbox-ids.json"
    code, out = await cli(target, "resolve-outbox", "--ids-file", str(ids_file))
    assert code == 0
    result = json.loads(out)
    assert (result["resolvable"], result["resolved"], result["apply"]) == (1, 0, False)
    assert str(document["_id"]) not in out
    assert await open_ids() == [entry]
    assert stat.S_IMODE(os.stat(ids_file).st_mode) == 0o600
    details = json.loads(ids_file.read_text())
    assert details["entries"][0]["id"] == entry
    assert details["entries"][0]["decision"] == "resolve"


async def test_group_limits_the_entries(target):
    identity = await open_entry("-")
    refdata = await open_entry("-", repository="AllowedOriginsRepository")
    code, result = await resolve_group(target, "refdata", "--apply")
    assert code == 0
    assert (result["in_scope"], result["out_of_scope"], result["resolved"]) == (1, 1, 1)
    assert await open_ids() == [identity]
    assert refdata not in await open_ids()


# -- the stuck case, end to end ----------------------------------------------------
async def test_after_the_tool_reconcile_and_verify_come_back_clean(target):
    """A group rolled back to dual after the ``--group`` postgres->mongo copy:
    its Postgres-side entry is still open, and a Mongo-first write whose
    Postgres mirror failed left an older application row. reconcile keeps
    that row while the entry is open, so verify never gets clean. After
    resolve-outbox --apply, reconcile copies Mongo's version and verify is
    clean."""
    dual = {"DB_WRITE_MODE": "dual"}
    document = session_document(user_agent="copied back by the --group run")
    await to_mongo(target, document)
    await to_postgres(document)
    await open_entry(str(document["_id"]))
    # dual: the write reaches Mongo, its Postgres mirror fails
    await to_mongo(
        target,
        {**document, "user_agent": "written after the rollback", "updated_at": later()},
    )

    code, out = await cli(target, "--collections", "sessions", "reconcile", env=dual)
    assert json.loads(out)["sessions"]["newer_in_postgres"] == 1
    async with Runner(target) as runner:
        assert not all(r.clean for r in await runner.verify())

    code, result = await resolve(target, "--apply")
    assert (code, result["resolved"]) == (0, 1)

    code, out = await cli(target, "reconcile", env=dual)
    assert code == 0 and json.loads(out)["sessions"]["fixed"] == 1
    async with Runner(target) as runner:
        reports = await runner.verify()
    assert all(r.clean for r in reports), [r.as_dict() for r in reports if not r.clean]
    async with container.pg_sessionmaker()() as session:
        row = await session.get(SessionRow, str(document["_id"]))
    assert row.doc["user_agent"] == "written after the rollback"
