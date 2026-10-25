"""verify and reconcile agree on what counts as a difference.

* Collections Mongo expires by a TTL index: an expired copy, in either store,
  is absent for verify as it is for reconcile. Copies Mongo's TTL monitor
  dropped while Postgres still holds them (or the reverse) are not reported
  forever as missing.
* A row the application wrote to Postgres after Mongo's copy (a session
  touched in Postgres): under a Mongo primary, reconcile copies Mongo's version
  over it, so the next verify is clean; under a Postgres primary it keeps the
  row and says so (``newer_in_postgres``) instead of reporting nothing.

These collections belong to groups served from Postgres only since 4.1, so
the CLI no longer verifies them; the engine still compares any collection it
is given, and a Mongo restored from 4.0 still has the TTL indexes, which the
fixture creates here. Skipped unless DATABASE_URL points at a *_test database."""

import contextlib
import datetime as dt
import io
import os

from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from pymongo import AsyncMongoClient

from backend.db.models import RateLimitCounterRow, SessionRow, WorkspaceTagRow
from backend.migrate.__main__ import build_target
from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum
from common.db.migrate import Runner

import pytest
import pytest_asyncio

NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
PAST = NOW - dt.timedelta(hours=1)
FUTURE = NOW + dt.timedelta(hours=1)


@pytest_asyncio.fixture
async def target(clean_postgres):
    target = build_target(os.environ["DATABASE_URL"])
    client = AsyncMongoClient(target.mongo_uri)
    database = client[target.mongo_db]
    for name in ("rate_limit_counters", "sessions", "workspace_tags"):
        await database[name].delete_many({})
    # 4.0 expired these by a TTL index; 4.1 no longer declares it
    await database["rate_limit_counters"].create_index(
        "expires_at", expireAfterSeconds=0
    )
    yield target
    for name in ("rate_limit_counters", "sessions", "workspace_tags"):
        await database[name].drop()
    await client.close()


def counter(expires_at, hits=1):
    return {
        "_id": PydanticObjectId(),
        "hits": hits,
        "expires_at": expires_at,
        "created_at": PAST,
        "updated_at": PAST,
    }


async def to_mongo(target, collection, document):
    client = AsyncMongoClient(target.mongo_uri)
    await client[target.mongo_db][collection].insert_one(dict(document))
    await client.close()


async def to_postgres(row_cls, document, *, updated_at=None):
    doc = canonical_document(document)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            row_cls(
                id=str(document["_id"]),
                doc=doc,
                created_at=document["created_at"],
                updated_at=updated_at or document["updated_at"],
                bc_source=SOURCE_APP,
                bc_checksum=checksum(doc),
            )
        )


async def verify(target, collection):
    async with Runner(target) as runner:
        (report,) = await runner.verify([collection])
    return report


# -- TTL collections ---------------------------------------------------------


async def test_expired_copies_only_in_postgres_are_absent(target):
    """Mongo's TTL index dropped them; Postgres still holds them."""
    for _ in range(3):
        await to_postgres(RateLimitCounterRow, counter(PAST))
    report = await verify(target, "rate_limit_counters")
    assert report.clean, report.as_dict()
    assert report.expired == 3
    assert report.postgres == 3  # the raw count still shows them


async def test_expired_copies_between_and_after_mongo_documents(target):
    """Expired Postgres-only copies inside Mongo's id range and past it, and
    an expired copy in both stores whose contents differ: all absent."""
    first = counter(FUTURE)
    await to_mongo(target, "rate_limit_counters", first)
    await to_postgres(RateLimitCounterRow, first)
    await to_postgres(RateLimitCounterRow, counter(PAST))  # inside the range
    both = counter(PAST)
    await to_mongo(target, "rate_limit_counters", both)
    await to_postgres(RateLimitCounterRow, {**both, "hits": 7})
    last = counter(FUTURE)
    await to_mongo(target, "rate_limit_counters", last)
    await to_postgres(RateLimitCounterRow, last)
    await to_postgres(RateLimitCounterRow, counter(PAST))  # past Mongo's last id
    report = await verify(target, "rate_limit_counters")
    assert report.clean, report.as_dict()
    assert report.expired == 4  # the copy in both stores counts twice


async def test_an_expired_copy_only_in_mongo_is_absent(target):
    await to_mongo(target, "rate_limit_counters", counter(PAST))
    report = await verify(target, "rate_limit_counters")
    assert report.clean, report.as_dict()


async def test_a_live_copy_missing_on_either_side_is_still_reported(target):
    only_pg = counter(FUTURE)
    await to_postgres(RateLimitCounterRow, only_pg)
    only_mongo = counter(FUTURE)
    await to_mongo(target, "rate_limit_counters", only_mongo)
    # live in Mongo, expired in Postgres: Postgres lacks the live copy
    renewed = counter(PAST)
    await to_postgres(RateLimitCounterRow, renewed)
    await to_mongo(target, "rate_limit_counters", {**renewed, "expires_at": FUTURE})
    report = await verify(target, "rate_limit_counters")
    assert not report.clean
    assert report.missing_in_mongo == 1
    assert report.samples["missing_in_mongo"] == [str(only_pg["_id"])]
    assert report.missing_in_postgres == 2
    assert set(report.samples["missing_in_postgres"]) == {
        str(only_mongo["_id"]),
        str(renewed["_id"]),
    }
    # and reconcile repairs what verify reports from Mongo's side
    async with Runner(target) as runner:
        result = await runner.reconcile(["rate_limit_counters"])
    assert result["rate_limit_counters"]["fixed"] == 2
    after = await verify(target, "rate_limit_counters")
    assert after.missing_in_postgres == 0
    assert after.missing_in_mongo == 1  # a live row Mongo never had


# -- a session touched in Postgres --------------------------------------------


def session_document():
    return {
        "_id": PydanticObjectId(),
        "user_id": "u1",
        "refresh_jti": "jti",
        "previous_refresh_jti": None,
        "rotated_at": None,
        "last_refreshed_at": PAST,
        "expires_at": NOW + dt.timedelta(days=7),
        "email_verified": True,
        "method": None,
        "scope": None,
        "scope_workspace_id": None,
        "user_agent": None,
        "revoked_at": None,
        "revoke_reason": None,
        "created_at": PAST,
        "updated_at": PAST,
    }


async def session_row(session_id):
    async with container.pg_sessionmaker()() as session:
        return (
            await session.execute(select(SessionRow).where(SessionRow.id == session_id))
        ).scalar_one()


async def test_a_newer_updated_at_column_alone_is_no_difference(target):
    """verify compares the ``_bc_checksum`` of the row's ``doc`` with the
    checksum of Mongo's document; the ``updated_at`` column is not part of it.
    reconcile agrees: it compares the same checksums and writes nothing."""
    document = session_document()
    await to_mongo(target, "sessions", document)
    await to_postgres(SessionRow, document, updated_at=NOW)
    report = await verify(target, "sessions")
    assert report.clean, report.as_dict()
    async with Runner(target) as runner:
        result = await runner.reconcile(["sessions"], mongo_primary=["identity"])
    assert result["sessions"]["fixed"] == 0


async def touched_in_postgres_only(target):
    """A session Mongo holds as of PAST, touched since in Postgres alone (a
    touch whose Mongo copy lost to another write, or two dumps taken apart)."""
    document = session_document()
    await to_mongo(target, "sessions", document)
    touched = {**document, "last_refreshed_at": NOW, "updated_at": NOW}
    await to_postgres(SessionRow, touched)
    report = await verify(target, "sessions")
    assert report.mismatched == 1 and report.drifted == 1, report.as_dict()
    return document


async def test_mongo_primary_reconcile_copies_mongo_over_a_newer_row(target):
    document = await touched_in_postgres_only(target)
    async with Runner(target) as runner:
        result = await runner.reconcile(["sessions"], mongo_primary=["identity"])
    assert result["sessions"]["fixed"] == 1
    assert result["sessions"]["newer_in_postgres"] == 0
    assert (await verify(target, "sessions")).clean
    row = await session_row(str(document["_id"]))
    assert row.doc == canonical_document(document)


async def test_postgres_primary_reconcile_keeps_a_newer_row_and_says_so(target):
    document = await touched_in_postgres_only(target)
    async with Runner(target) as runner:
        result = await runner.reconcile(["sessions"])  # no Mongo-primary group
    assert result["sessions"]["fixed"] == 0
    assert result["sessions"]["skipped"] == 0
    assert result["sessions"]["newer_in_postgres"] == 1
    row = await session_row(str(document["_id"]))
    assert row.doc["updated_at"] != canonical_document(document)["updated_at"]
    # the other direction makes them agree
    async with Runner(target) as runner:
        await runner.reconcile(["sessions"], direction="postgres->mongo")
    assert (await verify(target, "sessions")).clean


# -- through the CLI: a group still migrated on 4.1 (responses) ---------------


async def tag_edited_in_postgres_only(target):
    """A workspace tag Mongo holds as of PAST, renamed since in Postgres alone."""
    document = {
        "_id": PydanticObjectId(),
        "workspace_id": "w1",
        "title": "before",
        "created_at": PAST,
        "updated_at": PAST,
    }
    await to_mongo(target, "workspace_tags", document)
    await to_postgres(
        WorkspaceTagRow, {**document, "title": "after", "updated_at": NOW}
    )
    assert (await verify(target, "workspace_tags")).mismatched == 1
    return document


async def reconcile_cli(target, env, *extra):
    """``python -m backend.migrate reconcile`` over workspace_tags; its result."""
    import asyncio
    import json

    from common.db.migrate.cli import main

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = await asyncio.to_thread(
            main,
            ["--collections", "workspace_tags", "reconcile", *extra],
            target,
            prog="python -m backend.migrate",
            env=env,
        )
    assert code == 0
    return json.loads(out.getvalue())["workspace_tags"]


async def test_the_cli_lets_mongo_win_under_explicit_dual(target):
    await tag_edited_in_postgres_only(target)
    result = await reconcile_cli(target, {"DB_WRITE_MODE": "dual"}, "--mongo-wins")
    assert result["fixed"] == 1
    assert (await verify(target, "workspace_tags")).clean


async def test_the_cli_keeps_a_newer_row_without_mongo_wins(target):
    await tag_edited_in_postgres_only(target)
    result = await reconcile_cli(target, {"DB_WRITE_MODE": "dual"})
    assert (result["fixed"], result["newer_in_postgres"]) == (0, 1)


async def test_the_cli_keeps_a_newer_row_when_the_flags_are_missing(target):
    await tag_edited_in_postgres_only(target)
    result = await reconcile_cli(target, {}, "--mongo-wins")
    assert (result["fixed"], result["newer_in_postgres"]) == (0, 1)


async def test_the_cli_keeps_a_newer_row_of_a_postgres_primary_group(target):
    await tag_edited_in_postgres_only(target)
    env = {
        "DB_WRITE_MODE": "dual",
        "DB_WRITE_MODE__responses": "postgres_primary_dual",
        "DB_READ_SOURCE__responses": "postgres",
    }
    result = await reconcile_cli(target, env, "--mongo-wins")
    assert (result["fixed"], result["newer_in_postgres"]) == (0, 1)


async def test_rollback_window_writes_are_never_overwritten(target):
    """A group rolled back from postgres_primary_dual to dual: Postgres holds
    a write whose Mongo mirror failed (recorded in the Postgres-side outbox).
    Mongo must not win while that entry is open."""
    from backend.db.models import MirrorWriteFailure

    document = await tag_edited_in_postgres_only(target)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name="workspace_tags",
                row_id=str(document["_id"]),
                op="update",
                error="ConnectionError: store unreachable",
            )
        )
    result = await reconcile_cli(target, {"DB_WRITE_MODE": "dual"}, "--mongo-wins")
    assert (result["fixed"], result["newer_in_postgres"]) == (0, 1)
    async with container.pg_sessionmaker()() as session:
        row = await session.get(WorkspaceTagRow, str(document["_id"]))
        assert row.doc["title"] == "after"
        open_entries = (
            await session.execute(
                select(MirrorWriteFailure).where(
                    MirrorWriteFailure.resolved_at.is_(None)
                )
            )
        ).all()
    assert len(open_entries) == 1  # not drained: the row still differs


class WriteBeforeTheUpdate(Runner):
    """The application writes (Mongo first, then its mirror) after reconcile
    re-read Mongo and before it updates Postgres."""

    write = None

    async def _apply_to_postgres(self, table, writes):
        write, type(self).write = type(self).write, None
        if write is not None:
            await write()
        return await super()._apply_to_postgres(table, writes)


async def test_a_write_racing_mongo_wins_is_left_as_the_application_wrote_it(
    target,
):
    document = await tag_edited_in_postgres_only(target)
    later = NOW + dt.timedelta(minutes=1)
    raced = {**document, "title": "raced", "updated_at": later}

    async def app_write():
        client = AsyncMongoClient(target.mongo_uri)
        await client[target.mongo_db]["workspace_tags"].replace_one(
            {"_id": document["_id"]}, raced
        )
        await client.close()
        doc = canonical_document(raced)
        async with container.pg_sessionmaker()() as session, session.begin():
            row = await session.get(WorkspaceTagRow, str(document["_id"]))
            row.doc, row.bc_checksum, row.updated_at = doc, checksum(doc), later

    WriteBeforeTheUpdate.write = app_write
    async with WriteBeforeTheUpdate(target) as runner:
        result = await runner.reconcile(["workspace_tags"], mongo_primary=["responses"])
    assert (result["workspace_tags"]["fixed"], result["workspace_tags"]["skipped"]) == (
        0,
        1,
    )
    async with container.pg_sessionmaker()() as session:
        row = await session.get(WorkspaceTagRow, str(document["_id"]))
        assert row.doc == canonical_document(raced)
    assert (await verify(target, "workspace_tags")).clean


async def test_an_iso_string_expiry_is_a_live_copy(target):
    """Mongo's TTL monitor expires BSON dates only: a string never expires."""
    stringly = counter(PAST)
    stringly["expires_at"] = PAST.isoformat()
    await to_postgres(RateLimitCounterRow, stringly)
    report = await verify(target, "rate_limit_counters")
    assert report.missing_in_mongo == 1
    assert report.expired == 0
