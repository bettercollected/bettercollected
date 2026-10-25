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
import pytest_asyncio
from beanie import PydanticObjectId
from dependency_injector import providers
from pymongo import AsyncMongoClient
from sqlalchemy import select

from backend.app.container import AppContainer, container
from backend.db.groups import POSTGRES_ONLY_GROUPS, RETIRED_REPOSITORIES
from backend.db.models import DeletionTombstone, MirrorWriteFailure, WorkspaceTagRow
from backend.migrate.__main__ import build_target, repository_groups
from common.db import RoutingRepository
from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum
from common.db.migrate import Runner
from common.db.migrate.cli import main
from common.db.migrate.outbox import OutboxResolver

UTC = dt.timezone.utc
PAST = dt.datetime.now(UTC).replace(microsecond=0) - dt.timedelta(hours=1)


COLLECTION = "workspace_tags"  # group responses, still migrated on 4.1
REPOSITORY = "WorkspaceRespondersRepository"  # a responses repository


@pytest_asyncio.fixture
async def target(clean_postgres):
    target = build_target(os.environ["DATABASE_URL"])
    async with mongo(target) as db:
        await db[COLLECTION].drop()
    yield target
    async with mongo(target) as db:
        await db[COLLECTION].drop()


@contextlib.asynccontextmanager
async def mongo(target):
    client = AsyncMongoClient(target.mongo_uri, tz_aware=True)
    try:
        yield client[target.mongo_db]
    finally:
        await client.close()


def tag_document(**changes):
    return {
        "_id": PydanticObjectId(),
        "workspace_id": "w1",
        "title": None,
        "created_at": PAST,
        "updated_at": PAST,
        **changes,
    }


async def to_mongo(target, document):
    async with mongo(target) as db:
        await db[COLLECTION].replace_one(
            {"_id": document["_id"]}, document, upsert=True
        )


async def to_postgres(document, *, updated_at=PAST):
    doc = canonical_document(document)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            WorkspaceTagRow(
                id=str(document["_id"]),
                doc=doc,
                created_at=PAST,
                updated_at=updated_at,
                bc_source=SOURCE_APP,
                bc_checksum=checksum(doc),
            )
        )


async def open_entry(row_id, repository=REPOSITORY):
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
        if mongo_impl is not None:
            name = mongo_impl.provides.__name__
        else:
            name = provider.kwargs["postgres"].args[0].__name__
        assert groups[name] == provider.kwargs["group"]
        checked += 1
    assert checked >= 5  # forms and responses (4.1)
    assert groups[REPOSITORY] == "responses"


# -- resolving: proof only by default --------------------------------------------
async def test_entries_whose_writes_are_proven_in_mongo_are_resolved(target):
    same = tag_document(title="same in both")
    await to_mongo(target, same)
    await to_postgres(same)
    await open_entry(f"{same['_id']},jti")
    await open_entry("-")  # names nothing: the group's rows decide
    code, result = await resolve(target, "--apply")
    assert code == 0, result
    assert (result["in_scope"], result["resolvable"], result["resolved"]) == (2, 2, 2)
    assert result["resolvable_as_superseded"] == 0
    assert result["groups"]["responses"]["rows_differing"] == 0
    assert await open_ids() == []


async def test_a_later_mongo_copy_lacking_the_write_is_kept_unless_accepted(target):
    """Write W (Postgres primary) failed to mirror; after the rollback a
    Mongo-first save built from Mongo's copy, which lacks W, stamps a later
    time. That is no proof W is in Mongo: kept as ``superseded`` by default,
    resolved only with --accept-superseded."""
    before = tag_document(title="before W")
    await to_mongo(target, before)
    await to_postgres({**before, "title": "W"})
    entry = await open_entry(str(before["_id"]))
    await to_mongo(
        target,
        {**before, "workspace_id": "w2", "updated_at": later()},  # no W in it
    )
    code, result = await resolve(target, "--apply")
    assert (code, result["resolved"]) == (1, 0)
    assert result["kept"]["superseded"] == 1
    assert result["groups"]["responses"]["rows_superseded"] == 1
    assert await open_ids() == [entry]
    code, result = await resolve(target, "--apply", "--accept-superseded")
    assert (code, result["resolved"], result["resolvable_as_superseded"]) == (0, 1, 1)
    assert await open_ids() == []


async def test_entries_whose_writes_are_missing_stay_open(target):
    only_postgres = tag_document(title="never reached Mongo")
    await to_postgres(only_postgres)
    newer_in_postgres = tag_document()
    await to_mongo(target, newer_in_postgres)
    await to_postgres(
        {**newer_in_postgres, "title": "the Postgres write"},
        updated_at=PAST + dt.timedelta(minutes=5),
    )
    missing = await open_entry(str(only_postgres["_id"]))
    older = await open_entry(str(newer_in_postgres["_id"]))
    unnamed = await open_entry("-")
    other_group = await open_entry("-", repository="FormRepository")
    unknown = await open_entry("-", repository="NoSuchRepository")
    code, result = await resolve(target, "--apply", "--accept-superseded")
    assert code == 1
    assert {k: v for k, v in result["kept"].items() if v} == {
        "unknown_repository": 1,
        "missing_in_mongo": 1,
        "older_in_mongo": 1,
        "group_differs": 1,
    }
    assert result["groups"]["responses"]["rows_differing"] == 2
    assert result["resolved"] == 1  # the forms entry: nothing differs there
    assert await open_ids() == sorted([missing, older, unnamed, unknown])
    assert other_group not in await open_ids()


async def test_an_unnamed_newer_mongo_copy_older_than_the_entry_keeps_it(target):
    """A row the entry does not name, whose Mongo copy is later than the row
    but older than the entry: not even ``superseded`` for that entry."""
    document = tag_document()
    await to_mongo(
        target,
        {
            **document,
            "title": "a Mongo write before the entry",
            "updated_at": PAST + dt.timedelta(minutes=10),
        },
    )
    await to_postgres(document)
    entry = await open_entry("-")
    code, result = await resolve(target, "--apply", "--accept-superseded")
    assert (code, result["kept"]["group_differs"], result["resolved"]) == (1, 1, 0)
    assert await open_ids() == [entry]


async def test_an_unnamed_delete_without_a_tombstone_keeps_the_entry(target):
    """Mongo holds a copy Postgres lacks and no store recorded a delete:
    possibly a Postgres delete Mongo never got. Kept, named or not."""
    document = tag_document()
    await to_mongo(target, document)
    unnamed = await open_entry("-")
    named = await open_entry(str(document["_id"]))
    code, result = await resolve(target, "--apply", "--accept-superseded")
    assert code == 1
    assert (result["kept"]["group_differs"], result["kept"]["missing_in_postgres"]) == (
        1,
        1,
    )
    assert await open_ids() == sorted([unnamed, named])


async def test_a_mongo_copy_older_than_a_delete_keeps_the_entry(target):
    deleted = tag_document()
    await to_mongo(target, deleted)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            DeletionTombstone(
                collection=COLLECTION,
                row_id=str(deleted["_id"]),
                deleted_at=PAST + dt.timedelta(minutes=1),
            )
        )
    await open_entry(str(deleted["_id"]))
    code, result = await resolve(target)
    assert code == 1
    assert result["kept"]["delete_pending"] == 1


async def test_a_copy_expired_on_one_side_only_keeps_the_entry(target):
    """A Postgres row past the collection's TTL while Mongo's copy is live
    (renewed) is no proof (the TTL index is made here for the test)."""
    async with mongo(target) as db:
        await db[COLLECTION].create_index("expires_at", expireAfterSeconds=0)
    document = tag_document(expires_at=PAST)
    await to_postgres(document)
    await to_mongo(target, {**document, "expires_at": later() + dt.timedelta(days=1)})
    entry = await open_entry(str(document["_id"]))
    code, result = await resolve(target, "--apply", "--accept-superseded")
    assert (code, result["kept"]["expired_one_side"], result["resolved"]) == (1, 1, 0)
    assert await open_ids() == [entry]


async def test_entries_recorded_or_resolved_between_plan_and_apply(target):
    """apply resolves only the entries the plan proved, and only while they
    are still open: one recorded after the plan stays open, one resolved
    meanwhile is not counted again."""
    document = tag_document(title="same in both")
    await to_mongo(target, document)
    await to_postgres(document)
    first = await open_entry(str(document["_id"]))
    second = await open_entry("-")
    async with Runner(target) as runner:
        resolver = OutboxResolver(runner)
        plan = await resolver.plan()
        assert plan.resolvable == [first, second]
        recorded_after = await open_entry(str(document["_id"]))
        async with container.pg_sessionmaker()() as session, session.begin():
            entry = await session.get(MirrorWriteFailure, second)
            entry.resolved_at = dt.datetime.now(UTC)
        assert await resolver.apply(plan) == 1
    assert await open_ids() == [recorded_after]


async def test_the_dry_run_changes_nothing_and_ids_go_only_to_the_file(
    target, tmp_path
):
    document = tag_document(title="same in both")
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
    responses = await open_entry("-")
    forms = await open_entry("-", repository="FormRepository")
    code, result = await resolve_group(target, "forms", "--apply")
    assert code == 0
    assert (result["in_scope"], result["out_of_scope"], result["resolved"]) == (1, 1, 1)
    assert await open_ids() == [responses]
    assert forms not in await open_ids()


async def test_postgres_only_leftovers_are_counted_apart(target):
    """Entries of the repositories of groups served from Postgres only since
    4.1: counted as ``postgres_only_leftover``, never part of the exit code,
    resolved only with --clear-postgres-only-leftovers (and --apply); a
    ``--group`` naming such a group is refused."""
    leftover = await open_entry("-", repository="AllowedOriginsRepository")
    unknown = await open_entry("-", repository="NoSuchRepository")
    code, result = await resolve(target, "--apply")
    assert (code, result["postgres_only_leftover"], result["in_scope"]) == (1, 1, 1)
    assert result["kept"]["unknown_repository"] == 1
    assert await open_ids() == sorted([leftover, unknown])
    code, result = await resolve(target, "--clear-postgres-only-leftovers")
    assert result["leftover_cleared"] == 0  # a dry run
    code, result = await resolve(target, "--apply", "--clear-postgres-only-leftovers")
    assert result["leftover_cleared"] == 1
    assert await open_ids() == [unknown]
    with pytest.raises(SystemExit) as exc:
        await cli(target, "--group", "refdata", "resolve-outbox")
    assert exc.value.code == 2


def test_the_retired_repositories_are_postgres_only_and_routed_no_more():
    assert set(RETIRED_REPOSITORIES.values()) == set(POSTGRES_ONLY_GROUPS)
    assert not set(RETIRED_REPOSITORIES) & set(repository_groups())


# -- the stuck case, end to end ----------------------------------------------------
async def test_after_the_tool_reconcile_and_verify_come_back_clean(target):
    """A group rolled back to dual after the ``--group`` postgres->mongo copy:
    its Postgres-side entry is still open, and a Mongo-first write whose
    Postgres mirror failed left an older application row. reconcile keeps
    that row while the entry is open, so verify never gets clean. By default
    the tool keeps the entry (``superseded``: a later stamp is no proof);
    once the operator accepts Mongo's newer version, reconcile copies it and
    verify is clean."""
    dual = {"DB_WRITE_MODE": "dual"}
    document = tag_document(title="copied back by the --group run")
    await to_mongo(target, document)
    await to_postgres(document)
    await open_entry(str(document["_id"]))
    # dual: the write reaches Mongo, its Postgres mirror fails
    await to_mongo(
        target,
        {**document, "title": "written after the rollback", "updated_at": later()},
    )

    code, out = await cli(target, "--collections", COLLECTION, "reconcile", env=dual)
    assert json.loads(out)[COLLECTION]["newer_in_postgres"] == 1
    async with Runner(target) as runner:
        assert not all(r.clean for r in await runner.verify())

    code, result = await resolve(target, "--apply")
    assert (code, result["resolved"], result["kept"]["superseded"]) == (1, 0, 1)
    code, result = await resolve(target, "--apply", "--accept-superseded")
    assert (code, result["resolved"]) == (0, 1)

    code, out = await cli(target, "reconcile", env=dual)
    assert code == 0 and json.loads(out)[COLLECTION]["fixed"] == 1
    async with Runner(target) as runner:
        reports = await runner.verify()
    assert all(r.clean for r in reports), [r.as_dict() for r in reports if not r.clean]
    async with container.pg_sessionmaker()() as session:
        row = await session.get(WorkspaceTagRow, str(document["_id"]))
    assert row.doc["title"] == "written after the rollback"
