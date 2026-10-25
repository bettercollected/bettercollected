"""The "migration verified" marker, ``--group`` and ``status --json`` against both
real stores, plus what reconcile does with a row deleted on one side.
Skipped unless DATABASE_URL points at a *_test database."""

import json
import os

import pytest
from dependency_injector import providers
from sqlalchemy import select

from backend.app.container import AppContainer, container
from backend.app.schemas.template import FormTemplateDocument
from backend.db.groups import COLLECTION_GROUPS, GROUPS, POSTGRES_ONLY_GROUPS
from backend.db.models import AllowedOriginRow, MigrationProgress, MirrorWriteFailure
from backend.migrate.__main__ import _tables, build_target
from common.db import RoutingRepository, load_flags, write_op
from common.db.marker import SCOPE_GROUP, SCOPE_SERVICE, migration_verified
from common.db.migrate import Runner
from common.db.migrate.cli import (
    build_parser,
    main,
    reconcile_to_mongo_refusal,
    run,
)
from tests.app.db.beanie_originals import (
    AllowedOriginsDocument,
    AllowedOriginsRepository,
    PostgresAllowedOriginsRepository,
)


@pytest.fixture
def target(clean_postgres):
    return build_target(os.environ["DATABASE_URL"])


async def marker_rows():
    from backend.db.models import StoreMigration

    async with container.pg_engine().connect() as conn:
        rows = await conn.execute(
            select(StoreMigration.__table__).order_by(StoreMigration.__table__.c.id)
        )
        return [dict(r) for r in rows.mappings().all()]


async def current_marker():
    async with container.pg_engine().connect() as conn:
        return await migration_verified(conn, "backend")


def collections_of(group):
    return [c for c, g in COLLECTION_GROUPS.items() if g == group]


#: the groups verify covers and the marker rests on: all but the Postgres-only
MIGRATING = [g for g in GROUPS if g not in POSTGRES_ONLY_GROUPS]
POSTGRES_ONLY_COLLECTIONS = {
    c for c, g in COLLECTION_GROUPS.items() if g in POSTGRES_ONLY_GROUPS
}


async def add_origins(*origins):
    mongo = AllowedOriginsRepository()
    return [await mongo.add(o) for o in origins]


async def add_templates(*titles):
    """Form templates in Mongo only (the forms group, which verify covers)."""
    return [await FormTemplateDocument(title=t).save() for t in titles]


# -- the group map ------------------------------------------------------------
def test_every_migrated_collection_has_a_valid_group():
    assert set(COLLECTION_GROUPS) == set(_tables())
    assert set(COLLECTION_GROUPS.values()) == set(GROUPS)


def test_the_group_map_matches_the_routed_repositories():
    """A collection belongs to the group of the routed repository whose
    Postgres twin stores it, so ``--group g`` moves what ``DB_*__g`` moves."""
    checked = 0
    for name, provider in AppContainer.providers.items():
        if not isinstance(provider, providers.Singleton):
            continue
        if provider.provides is not RoutingRepository:
            continue
        group, twin = provider.kwargs["group"], provider.kwargs.get("postgres")
        # the groups served from Postgres only are not routed any more
        assert group not in POSTGRES_ONLY_GROUPS, f"{name} is still routed"
        if twin is None:
            continue
        cls = twin.args[0]
        rows = [cls.row, *getattr(cls, "document_rows", {}).values()]
        for row in rows:
            assert (
                COLLECTION_GROUPS[row.mongo_collection()] == group
            ), f"{name}: {row.__tablename__} is in group {group!r}"
            checked += 1
    assert checked > 10


# -- the marker ---------------------------------------------------------------
async def test_backfill_never_writes_and_a_clean_full_verify_writes_the_marker(target):
    await add_templates("w1", "w2")
    async with Runner(target) as runner:
        await runner.backfill()
        assert await marker_rows() == []
        reports = await runner.verify(list(target.migrating_tables()))
        outcome = await runner.record_verify(reports)
    assert outcome["marker"] == "written" and outcome["groups"] == MIGRATING
    marker = await current_marker()
    assert marker is not None and not marker.combined
    assert marker.collections["form_templates"] == {
        "group": "forms",
        "mongo": 2,
        "postgres": 2,
    }
    # the Postgres-only groups are imported, never verified: not in the marker
    assert set(marker.collections) == set(_tables()) - POSTGRES_ONLY_COLLECTIONS
    assert list(marker.groups) == MIGRATING
    assert "+schema.0021" in marker.code_version
    assert marker.run_id == runner.run_id
    rows = await marker_rows()
    assert sorted(r["scope"] for r in rows) == [SCOPE_GROUP] * len(MIGRATING) + [
        SCOPE_SERVICE
    ]


async def test_a_dirty_group_blocks_the_marker_until_reconciled(target):
    await add_origins("https://a.example")
    async with Runner(target) as runner:
        await runner.backfill()
    # written to Mongo only, after the backfill: missing in Postgres
    await FormTemplateDocument(title="W").save()
    async with Runner(target) as runner:
        outcome = await runner.record_verify(await runner.verify())
        assert "forms" not in outcome["groups"] and "responses" in outcome["groups"]
        assert outcome["marker"] is None
        assert await current_marker() is None
        await runner.reconcile(["form_templates"])
        outcome = await runner.record_verify(await runner.verify())
    assert outcome["marker"] == "written"
    assert (await current_marker()).collections["form_templates"]["postgres"] == 1


async def test_sampled_and_collection_subset_verifies_are_not_recorded(target):
    async with Runner(target) as runner:
        reports = await runner.verify(sample_every=2)
        assert (await runner.record_verify(reports, sample_every=2))["reason"]
        reports = await runner.verify(["allowed_origins"])
        assert (await runner.record_verify(reports, subset=True))["reason"]
    assert await marker_rows() == []


async def test_per_group_verifies_combine_into_the_marker(target):
    await add_templates("w1")
    async with Runner(target) as runner:
        await runner.backfill()
    outcomes = []
    for group in MIGRATING:
        async with Runner(target) as runner:
            outcomes.append(
                await runner.record_verify(await runner.verify(collections_of(group)))
            )
    assert [o["groups"] for o in outcomes] == [[g] for g in MIGRATING]
    assert [o["marker"] for o in outcomes] == [None] * (len(MIGRATING) - 1) + [
        "combined"
    ]
    marker = await current_marker()
    assert marker.combined and [b["group"] for b in marker.based_on] == MIGRATING
    group_rows = [r for r in await marker_rows() if r["scope"] == SCOPE_GROUP]
    assert marker.verified_at == min(r["verified_at"] for r in group_rows)
    assert marker.collections["form_templates"]["mongo"] == 1
    assert not set(marker.collections) & POSTGRES_ONLY_COLLECTIONS


async def test_a_backfill_after_a_group_verify_keeps_it_out_of_the_combination(
    target,
):
    await add_templates("w1")
    async with Runner(target) as runner:
        await runner.backfill()
    first, *rest = MIGRATING
    async with Runner(target) as runner:
        await runner.record_verify(await runner.verify(collections_of(first)))
        # the first group is backfilled again after its verify
        await runner.backfill(collections_of(first), restart=True)
        for group in rest:
            outcome = await runner.record_verify(
                await runner.verify(collections_of(group))
            )
    assert outcome["marker"] is None
    assert "backfilled after its last clean verify" in outcome["reason"]
    assert await current_marker() is None


async def test_verify_sees_a_postgres_row_before_the_first_mongo_id(target):
    """A Postgres-only row whose id sorts below every Mongo id was outside each
    batch's id range; verify now counts it, so it cannot pass as clean."""
    postgres = PostgresAllowedOriginsRepository(container.pg_sessionmaker())
    orphan = await postgres.add("https://only-in-postgres.example")
    await add_origins("https://a.example", "https://b.example")
    async with Runner(target) as runner:
        await runner.backfill(["allowed_origins"])
        (report,) = await runner.verify(["allowed_origins"])
    assert report.missing_in_mongo == 1
    assert report.samples["missing_in_mongo"] == [str(orphan.id)]
    assert not report.clean


# -- reconcile and deletes ----------------------------------------------------
class MongoDeleteFails(AllowedOriginsRepository):
    @write_op
    async def delete_by_origin(self, origin: str) -> None:
        raise ConnectionError("mongo unavailable")


@pytest.mark.allow_mirror_failures
async def test_reconcile_completes_a_postgres_delete_whose_mongo_mirror_failed(target):
    """Under postgres_primary_dual a delete whose Mongo mirror failed leaves the
    document in Mongo and an outbox row in Postgres. The delete left a
    tombstone, so verify reports the document as a deleted record still
    present, ``reconcile --direction postgres->mongo`` deletes it from Mongo
    (and drains the outbox), and it never comes back into Postgres."""
    repo = RoutingRepository(
        group="refdata",
        flags=load_flags(
            {"DB_WRITE_MODE": "postgres_primary_dual", "DB_READ_SOURCE": "postgres"}
        ),
        mongo=MongoDeleteFails(),
        postgres=PostgresAllowedOriginsRepository(container.pg_sessionmaker()),
        on_mirror_failure=container.outbox_recorder(),
    )
    kept = await repo.add("https://kept.example")
    gone = await repo.add("https://deleted.example")
    assert await AllowedOriginsDocument.get(gone.id) is not None  # mirrored
    await repo.delete_by_origin("https://deleted.example")

    async with container.pg_engine().connect() as conn:
        ids = (await conn.execute(select(AllowedOriginRow.id))).scalars().all()
        outbox = (await conn.execute(select(MirrorWriteFailure))).all()
    assert ids == [str(kept.id)]
    assert [(o.op, o.resolved_at) for o in outbox] == [("delete_by_origin", None)]

    async with Runner(target) as runner:
        (before,) = await runner.verify(["allowed_origins"])
        assert before.missing_in_postgres == 1 and before.tombstoned == 1
        # the kept row agrees: its replay stored the row's document exactly
        assert before.mismatched == 0
        result = await runner.reconcile(direction="postgres->mongo")
        assert result["allowed_origins"]["deleted"] == 1
        assert result["allowed_origins"]["fixed"] == 0
        (after,) = await runner.verify(["allowed_origins"])
    collection = AllowedOriginsDocument.get_pymongo_collection()
    assert await collection.find_one({"_id": gone.id}) is None
    assert after.clean
    async with container.pg_engine().connect() as conn:
        resolved = (await conn.execute(select(MirrorWriteFailure.resolved_at))).all()
    assert all(r[0] is not None for r in resolved)

    async with Runner(target) as runner:
        await runner.reconcile(["allowed_origins"], direction="mongo->postgres")
    async with container.pg_engine().connect() as conn:
        ids = (await conn.execute(select(AllowedOriginRow.id))).scalars().all()
    assert ids == [str(kept.id)]  # the deleted row did not come back


async def test_a_partial_reconcile_leaves_the_outbox_alone(target):
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name="FormTemplateRepository", row_id="x", op="save", error="E"
            )
        )
    async with Runner(target) as runner:
        await runner.reconcile(["allowed_origins"])
        assert (await runner.status())["outbox"]["postgres"] == 1
        # a mongo->postgres run never resolves the Postgres-side outbox
        await runner.reconcile()
        assert (await runner.status())["outbox"]["postgres"] == 1
        await runner.reconcile(direction="postgres->mongo")
        assert (await runner.status())["outbox"]["postgres"] == 0


# -- the CLI ------------------------------------------------------------------
def _args(*argv):
    return build_parser("python -m backend.migrate").parse_args(list(argv))


async def test_cli_group_verify_records_the_group_and_status_json(target, capsys):
    await add_templates("w1")
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name="FormTemplateRepository", row_id="x", op="save", error="E"
            )
        )
    assert await run(_args("--group", "forms", "backfill"), target) == 0
    assert await run(_args("--group", "forms", "verify"), target) == 0
    capsys.readouterr()
    rows = await marker_rows()
    assert [(r["scope"], r["groups"]) for r in rows] == [(SCOPE_GROUP, ["forms"])]

    assert await run(_args("status", "--json"), target) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["format"] == 1 and report["service"] == "backend"
    assert report["collections"]["form_templates"] == {
        "group": "forms",
        "mongo": 1,
        "postgres": 1,
        "backfill": report["collections"]["form_templates"]["backfill"],
    }
    assert report["collections"]["form_templates"]["backfill"]["state"] == "done"
    assert report["groups"]["forms"]["last_verify"]["run_id"] == rows[0]["run_id"]
    assert report["groups"]["responses"]["last_verify"] is None
    # status still covers the Postgres-only groups (their import)
    assert report["collections"]["allowed_origins"]["group"] == "refdata"
    assert report["last_verify"]["scope"] == SCOPE_GROUP
    assert report["marker"] is None
    assert report["outbox"] == {"mongo": 0, "postgres": 1}
    assert report["mirror_failures"]["postgres"] == {
        "total": 1,
        "unresolved": 1,
        "unresolved_by_method": {"FormTemplateRepository.save": 1},
    }
    assert report["mirror_failures"]["mongo"]["unresolved"] == 0

    assert await run(_args("--group", "forms", "status"), target) == 0
    text = capsys.readouterr().out
    assert "group forms: last clean verify" in text and "group responses" not in text


# -- verify and reconcile leave the Postgres-only groups alone -----------------
DIRECTIONS = ["mongo->postgres", "postgres->mongo"]
PPD = {"DB_WRITE_MODE": "postgres_primary_dual", "DB_READ_SOURCE": "postgres"}


def _command(name, direction):
    return ["verify"] if name == "verify" else ["reconcile", "--direction", direction]


@pytest.mark.parametrize(
    "name,direction",
    [("verify", None)] + [("reconcile", d) for d in DIRECTIONS],
    ids=["verify"] + [f"reconcile {d}" for d in DIRECTIONS],
)
async def test_verify_and_reconcile_skip_the_postgres_only_groups_and_say_so(
    target, capsys, name, direction
):
    """Mongo data of a Postgres-only group (here: allowed origins never
    imported) is neither compared nor copied, and the output says so."""
    await add_origins("https://a.example")
    args = _args(*_command(name, direction))
    assert reconcile_to_mongo_refusal(args, target, PPD) is None
    await run(args, target)
    captured = capsys.readouterr()
    assert (
        f"{name}: skipping the refdata, identity, actions, ai and analytics group(s), "
        "served from Postgres only" in captured.err
    )
    covered = (
        {r["collection"] for r in json.loads(captured.out)}
        if (name == "verify")
        else set(json.loads(captured.out))
    )
    assert covered == set(target.migrating_tables())
    assert not covered & POSTGRES_ONLY_COLLECTIONS
    async with container.pg_engine().connect() as conn:
        origins = (await conn.execute(select(AllowedOriginRow.id))).all()
    assert origins == []  # never copied
    if name == "verify":
        assert list((await current_marker()).groups) == MIGRATING


@pytest.mark.parametrize("group", POSTGRES_ONLY_GROUPS)
@pytest.mark.parametrize(
    "name,direction",
    [("verify", None)] + [("reconcile", d) for d in DIRECTIONS],
    ids=["verify"] + [f"reconcile {d}" for d in DIRECTIONS],
)
def test_verify_and_reconcile_refuse_a_postgres_only_group_by_name(
    target, capsys, name, direction, group
):
    """Exit 2, naming the group, before anything is opened; also under the
    services' postgres_primary_dual flags, which used to let it through."""
    for env in ({}, PPD):
        with pytest.raises(SystemExit) as exit_:
            main(
                ["--group", group, *_command(name, direction)],
                target,
                prog="python -m backend.migrate",
                env=env,
            )
        assert exit_.value.code == 2
        assert f"served from Postgres only: {group}" in capsys.readouterr().err


def test_reconcile_to_mongo_reads_the_backend_flags(target):
    """The backend's own loader decides each group's mode: a stale flag for a
    Postgres-only group refuses, as it refuses the services' start."""
    args = _args("reconcile", "--direction", "postgres->mongo")
    refusal = reconcile_to_mongo_refusal(
        args, target, {**PPD, "DB_WRITE_MODE__ai": "dual"}
    )
    assert refusal and "DB_WRITE_MODE__ai='dual'" in refusal


async def test_progress_is_untouched_by_verify(target):
    async with Runner(target) as runner:
        await runner.record_verify(await runner.verify())
    async with container.pg_engine().connect() as conn:
        assert (await conn.execute(select(MigrationProgress))).all() == []
    assert await current_marker() is not None
    # a later backfill does not revoke a full marker (it is a record, not a lease)
    await add_origins("https://late.example")
    async with Runner(target) as runner:
        await runner.backfill(["allowed_origins"])
    assert await current_marker() is not None
