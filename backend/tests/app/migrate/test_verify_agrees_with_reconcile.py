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
fixture creates here. The CLI cases at the end run on the test Target of
routed.py, for which ``responses`` still migrates. Skipped unless DATABASE_URL points at a *_test database."""

import contextlib
import dataclasses
import datetime as dt
import io
import os

from common.ids import RecordId
from sqlalchemy import select

from backend.app.container import container
from pymongo import AsyncMongoClient

from backend.db.models import RateLimitCounterRow, SessionRow, WorkspaceTagRow
from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum
from common.db.migrate import Runner
from tests.app.migrate.routed import build_target

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
        "_id": RecordId(),
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
    assert (report.expired_mongo, report.expired_postgres) == (0, 3)
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
    assert (report.expired_mongo, report.expired_postgres) == (1, 3)


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
        "_id": RecordId(),
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
        "_id": RecordId(),
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


# -- the Postgres-side outbox (writes from a time Postgres was primary) --------


async def open_postgres_entry(table_name="SessionRepository"):
    from backend.db.models import MirrorWriteFailure

    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name=table_name, row_id="x", op="touch", error="E: test"
            )
        )


async def outbox_open():
    async with Runner(build_target(os.environ["DATABASE_URL"])) as runner:
        return (await runner.status())["outbox"]


async def session_differing_in_postgres(target, *, updated_at, mongo_updated=True):
    """Same session in both stores; Postgres's document differs and its
    ``updated_at`` column is ``updated_at`` (equal to Mongo's, or NULL)."""
    document = session_document()
    mongo = dict(document)
    if not mongo_updated:
        del mongo["updated_at"]
    await to_mongo(target, "sessions", mongo)
    changed = {**document, "user_agent": "written while Postgres was primary"}
    doc = canonical_document(changed)
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
    return document, doc


@pytest.mark.parametrize(
    "updated_at,mongo_updated",
    [(PAST, True), (None, True), (PAST, False)],
    ids=["equal", "null-column", "no-mongo-updated-at"],
)
async def test_an_open_postgres_outbox_keeps_every_app_row(
    target, updated_at, mongo_updated
):
    """Default path (no --mongo-wins): timestamps that would let Mongo's copy
    through (equal, NULL, missing) do not, while the outbox is open."""
    document, doc = await session_differing_in_postgres(
        target, updated_at=updated_at, mongo_updated=mongo_updated
    )
    await open_postgres_entry()
    async with Runner(target) as runner:
        result = (await runner.reconcile(["sessions"]))["sessions"]
    assert (result["fixed"], result["newer_in_postgres"]) == (0, 1)
    assert (await session_row(str(document["_id"]))).doc == doc
    assert (await outbox_open())["postgres"] == 1


async def test_an_empty_postgres_outbox_keeps_todays_repairs(target):
    document, _ = await session_differing_in_postgres(target, updated_at=PAST)
    async with Runner(target) as runner:
        result = (await runner.reconcile(["sessions"]))["sessions"]
    assert result["fixed"] == 1
    assert (await session_row(str(document["_id"]))).doc == canonical_document(
        document
    )


async def test_an_open_postgres_outbox_still_repairs_backfilled_rows(target):
    document = session_document()
    await to_mongo(target, "sessions", document)
    stale = canonical_document({**document, "user_agent": "stale backfill"})
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            SessionRow(
                id=str(document["_id"]),
                doc=stale,
                created_at=PAST,
                updated_at=NOW,
                bc_source="backfill",
                bc_checksum=checksum(stale),
            )
        )
    await open_postgres_entry()
    async with Runner(target) as runner:
        result = (await runner.reconcile(["sessions"]))["sessions"]
    assert result["fixed"] == 1


async def test_mongo_to_postgres_never_resolves_the_postgres_outbox(target):
    """A full mongo->postgres pass resolves the Mongo-side outbox (mirror
    writes to Postgres it repaired), never the Postgres-side one: those rows
    may still be missing in Mongo."""
    await open_postgres_entry()
    client = AsyncMongoClient(target.mongo_uri)
    await client[target.mongo_db]["mirror_write_failures"].insert_one(
        {
            "table_name": "SessionRepository",
            "row_id": "y",
            "op": "touch",
            "error": "E: test",
            "attempts": 0,
            "resolved_at": None,
        }
    )
    await client.close()
    async with Runner(target) as runner:
        await runner.reconcile()
    assert await outbox_open() == {"mongo": 0, "postgres": 1}


async def test_a_clean_full_verify_resolves_the_postgres_outbox(target):
    await open_postgres_entry()
    async with Runner(target) as runner:
        outcome = await runner.record_verify(await runner.verify())
    assert outcome["marker"] == "written"
    assert (await outbox_open())["postgres"] == 0


async def bulk_counters(n, expires_at):
    rows = []
    for i in range(n):
        document = counter(expires_at(i))
        doc = canonical_document(document)
        rows.append(
            {
                "id": str(document["_id"]),
                "doc": doc,
                "created_at": PAST,
                "updated_at": PAST,
                "_bc_source": SOURCE_APP,
                "_bc_checksum": checksum(doc),
            }
        )
    table = RateLimitCounterRow.__table__
    async with container.pg_engine().begin() as conn:
        await conn.execute(table.insert(), rows)
    return sorted(r["id"] for r in rows)


async def test_rows_past_mongo_are_counted_across_batches(target):
    """More than one batch of 500 past Mongo's last id: none skipped or
    counted twice (live and expired interleaved)."""
    ids = await bulk_counters(1203, lambda i: PAST if i % 3 == 0 else FUTURE)
    report = await verify(target, "rate_limit_counters")
    assert report.expired == 401
    assert report.expired_postgres == 401
    assert report.missing_in_mongo == 802
    assert report.samples["missing_in_mongo"] == [
        i for i in ids if i in set(report.samples["missing_in_mongo"])
    ]


async def test_postgres_to_mongo_copies_rows_past_mongo_across_batches(target):
    ids = await bulk_counters(1203, lambda i: FUTURE)
    async with Runner(target) as runner:
        result = await runner.reconcile(
            ["rate_limit_counters"], direction="postgres->mongo"
        )
    assert result["rate_limit_counters"]["fixed"] == 1203
    client = AsyncMongoClient(target.mongo_uri)
    copied = await client[target.mongo_db]["rate_limit_counters"].distinct("_id")
    await client.close()
    assert sorted(str(i) for i in copied) == ids
    assert (await verify(target, "rate_limit_counters")).clean


async def test_a_clean_verify_compares_entries_on_the_database_clock(target):
    """verify's start time comes from Postgres, the clock the outbox's
    created_at uses: an entry recorded after it stays open, even when the
    runner's own clock is ahead."""
    from unittest import mock

    from backend.db.models import MirrorWriteFailure

    ahead = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)

    class Ahead(dt.datetime, metaclass=SkewedClockType):
        @classmethod
        def now(cls, tz=None):
            return ahead

    async with Runner(target) as runner:
        with mock.patch("common.db.migrate.engine.datetime", Ahead):
            reports = await runner.verify()
        started = runner._verify_started
        assert started < ahead - dt.timedelta(minutes=30)  # not the runner's clock
        async with container.pg_sessionmaker()() as session, session.begin():
            for row_id, at in (
                ("before", started - dt.timedelta(seconds=1)),
                ("after", started + dt.timedelta(seconds=1)),
            ):
                session.add(
                    MirrorWriteFailure(
                        table_name="SessionRepository",
                        row_id=row_id,
                        op="touch",
                        error="E: test",
                        created_at=at,
                    )
                )
        outcome = await runner.record_verify(reports)
    assert outcome["marker"] == "written"
    async with container.pg_sessionmaker()() as session:
        open_ids = (
            (
                await session.execute(
                    select(MirrorWriteFailure.row_id).where(
                        MirrorWriteFailure.resolved_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert open_ids == ["after"]


# -- recording a verify with expired copies ------------------------------------


def migrating_analytics(target):
    """``target`` with the analytics group (rate-limit counters, a TTL
    collection) still migrating, as on 4.0: the CLI verifies it there."""
    return dataclasses.replace(
        target,
        postgres_only_groups=tuple(
            g for g in target.postgres_only_groups if g != "analytics"
        ),
    )


async def stored_marker_rows():
    from backend.db.models import StoreMigration

    table = StoreMigration.__table__
    async with container.pg_engine().connect() as conn:
        rows = await conn.execute(select(table).order_by(table.c.id))
        return [dict(r) for r in rows.mappings().all()]


async def test_expired_postgres_only_copies_do_not_block_the_record(target):
    """Mongo's TTL monitor dropped every copy, Postgres still holds them: the
    group (and the marker) is recorded on the live counts."""
    target = migrating_analytics(target)
    for _ in range(3):
        await to_postgres(RateLimitCounterRow, counter(PAST))
    async with Runner(target) as runner:
        outcome = await runner.record_verify(await runner.verify())
    assert outcome["marker"] == "written", outcome
    assert "analytics" in outcome["groups"]
    service = [r for r in await stored_marker_rows() if r["scope"] == "service"]
    assert service[-1]["collections"]["rate_limit_counters"] == {
        "group": "analytics",
        "mongo": 0,
        "postgres": 0,
        "expired_mongo": 0,
        "expired_postgres": 3,
    }


async def test_expired_copies_in_both_stores_do_not_block_the_record(target):
    """Live copies in both stores, expired ones in both (one held by both,
    the others by one store each): recorded, live counts equal."""
    target = migrating_analytics(target)
    for _ in range(2):
        live = counter(FUTURE)
        await to_mongo(target, "rate_limit_counters", live)
        await to_postgres(RateLimitCounterRow, live)
    both = counter(PAST)
    await to_mongo(target, "rate_limit_counters", both)
    await to_postgres(RateLimitCounterRow, both)
    await to_mongo(target, "rate_limit_counters", counter(PAST))
    for _ in range(4):
        await to_postgres(RateLimitCounterRow, counter(PAST))
    async with Runner(target) as runner:
        reports = await runner.verify(target.collections_of("analytics"))
        (report,) = [r for r in reports if r.collection == "rate_limit_counters"]
        assert report.clean, report.as_dict()
        assert (report.mongo, report.postgres) == (4, 7)
        assert (report.expired_mongo, report.expired_postgres) == (2, 5)
        outcome = await runner.record_verify(reports)
    assert outcome["groups"] == ["analytics"], outcome
    (row,) = [r for r in await stored_marker_rows() if r["scope"] == "group"]
    recorded = row["collections"]["rate_limit_counters"]
    assert (recorded["mongo"], recorded["postgres"]) == (2, 2)
    assert (recorded["expired_mongo"], recorded["expired_postgres"]) == (2, 5)


async def test_unequal_live_counts_still_refuse_the_record(target):
    """A live count that differs (here: a copy written between the count and
    the merge-join) still keeps the group from being recorded."""
    target = migrating_analytics(target)
    live = counter(FUTURE)
    await to_mongo(target, "rate_limit_counters", live)
    await to_postgres(RateLimitCounterRow, live)
    await to_postgres(RateLimitCounterRow, counter(PAST))
    async with Runner(target) as runner:
        reports = await runner.verify()
        (report,) = [r for r in reports if r.collection == "rate_limit_counters"]
        assert report.clean and report.expired_postgres == 1
        report.mongo += 1
        outcome = await runner.record_verify(reports)
    assert "analytics" not in outcome["groups"], outcome
    assert outcome["marker"] is None


# -- counts taken at one moment, on the database clock ---------------------------


async def record(target):
    """verify (everything the target migrates) then record it."""
    async with Runner(target) as runner:
        reports = await runner.verify()
        (report,) = [r for r in reports if r.collection == "rate_limit_counters"]
        return report, await runner.record_verify(reports)


@pytest.fixture
def ttl_deleted_after_count(monkeypatch):
    """Mongo's TTL monitor deleting the expired copies right after verify
    counted them, before it scanned."""
    original = Runner._count_mongo

    async def counted(self, coll, ttl):
        result = await original(self, coll, ttl)
        await coll.delete_many({"expires_at": {"$lte": result[2]}})
        return result

    monkeypatch.setattr(Runner, "_count_mongo", counted)


async def both_stores(target, expires_at):
    document = counter(expires_at)
    await to_mongo(target, "rate_limit_counters", document)
    await to_postgres(RateLimitCounterRow, document)
    return document


async def test_copies_the_ttl_monitor_drops_mid_run_still_record_clean(
    target, ttl_deleted_after_count
):
    """Counted as expired together with the raw count: the scan no longer
    finds them in Mongo, and the live counts still agree."""
    target = migrating_analytics(target)
    await both_stores(target, FUTURE)
    for _ in range(2):
        await both_stores(target, PAST)
    report, outcome = await record(target)
    assert report.clean, report.as_dict()
    assert (report.mongo, report.expired_mongo) == (3, 2)
    assert (report.postgres, report.expired_postgres) == (3, 2)
    assert "analytics" in outcome["groups"], outcome
    assert outcome["marker"] == "written", outcome


async def test_a_live_difference_still_refuses_beside_mid_run_deletions(
    target, ttl_deleted_after_count
):
    """The same run, with a live copy only Mongo holds: refused."""
    target = migrating_analytics(target)
    await both_stores(target, PAST)
    await to_mongo(target, "rate_limit_counters", counter(FUTURE))
    report, outcome = await record(target)
    assert not report.clean
    assert report.missing_in_postgres == 1
    assert "analytics" not in outcome["groups"], outcome
    assert outcome["marker"] is None


class TtlDeletesWhileCounting:
    """``coll`` whose raw count is followed by the TTL monitor dropping one
    expired copy (``times`` times at most)."""

    def __init__(self, coll, times):
        self._coll, self._times = coll, times

    def __getattr__(self, name):
        return getattr(self._coll, name)

    async def count_documents(self, query, *args, **kwargs):
        found = await self._coll.count_documents(query, *args, **kwargs)
        if not query and self._times:
            self._times -= 1
            doomed = await self._coll.find_one({"expires_at": {"$lte": NOW}})
            if doomed:
                await self._coll.delete_one({"_id": doomed["_id"]})
        return found


def ttl_deletes_while_counting(monkeypatch, times):
    original = Runner.collection

    def collection(self, name):
        return TtlDeletesWhileCounting(original(self, name), times)

    monkeypatch.setattr(Runner, "collection", collection)


async def test_a_raw_count_overtaken_by_the_ttl_monitor_is_taken_again(
    target, monkeypatch
):
    target = migrating_analytics(target)
    await both_stores(target, FUTURE)
    for _ in range(3):
        await both_stores(target, PAST)
    ttl_deletes_while_counting(monkeypatch, 1)
    report, outcome = await record(target)
    assert report.clean and not report.count_unstable, report.as_dict()
    assert (report.live_mongo, report.live_postgres) == (1, 1)
    assert "analytics" in outcome["groups"], outcome


async def test_counts_that_never_settle_are_not_clean(target, monkeypatch):
    """The monitor keeps deleting between the counts: not recorded, however
    the numbers come out."""
    from common.db.migrate import engine

    target = migrating_analytics(target)
    await both_stores(target, FUTURE)
    for _ in range(engine.COUNT_ATTEMPTS + 1):
        await both_stores(target, PAST)
    ttl_deletes_while_counting(monkeypatch, engine.COUNT_ATTEMPTS)
    report, outcome = await record(target)
    assert report.count_unstable and not report.clean
    assert "analytics" not in outcome["groups"], outcome
    assert outcome["marker"] is None


async def test_non_objectid_copies_are_caught_by_the_count_not_the_scan(target):
    """The scan only walks ObjectIds: a live copy under another kind of id is
    caught by the counts alone."""
    target = migrating_analytics(target)
    await to_mongo(target, "rate_limit_counters", {**counter(FUTURE), "_id": "legacy"})
    report, outcome = await record(target)
    assert report.clean  # the scan saw nothing to compare
    assert (report.live_mongo, report.live_postgres) == (1, 0)
    assert "analytics" not in outcome["groups"], outcome
    assert outcome["marker"] is None


async def test_expired_non_objectid_copies_are_absent(target):
    target = migrating_analytics(target)
    await to_mongo(target, "rate_limit_counters", {**counter(PAST), "_id": "legacy"})
    report, outcome = await record(target)
    assert (report.mongo, report.expired_mongo) == (1, 1)
    assert "analytics" in outcome["groups"], outcome


class SkewedClockType(type):
    def __instancecheck__(cls, instance):
        return isinstance(instance, dt.datetime)


def skewed_clock(skew):
    """``datetime`` as the runner's host sees it: ``now`` off by ``skew``."""

    class Clock(dt.datetime, metaclass=SkewedClockType):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime.now(tz) + skew

    return Clock


@pytest.mark.parametrize("skew", [dt.timedelta(hours=3), -dt.timedelta(hours=3)])
async def test_the_host_clock_does_not_decide_what_has_expired(target, skew):
    """A runner clock hours ahead or behind: a copy expiring in an hour is
    live, one that expired an hour ago is expired, as on Mongo's clock."""
    from unittest import mock

    target = migrating_analytics(target)
    await both_stores(target, FUTURE)
    await both_stores(target, PAST)
    with mock.patch("common.db.migrate.engine.datetime", skewed_clock(skew)):
        report, outcome = await record(target)
    assert report.clean, report.as_dict()
    assert (report.expired_mongo, report.expired_postgres) == (1, 1)
    assert "analytics" in outcome["groups"], outcome
