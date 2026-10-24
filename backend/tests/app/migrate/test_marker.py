"""The "migration verified" marker, ``--group`` and ``status --json`` against both
real stores, plus what reconcile does with a row deleted on one side.
Skipped unless DATABASE_URL points at a *_test database."""

import json
import os

import pytest
from dependency_injector import providers
from sqlalchemy import select

from backend.app.container import AppContainer, container
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.postgres.refdata import PostgresAllowedOriginsRepository
from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.db.groups import COLLECTION_GROUPS, GROUPS
from backend.db.models import AllowedOriginRow, MigrationProgress, MirrorWriteFailure
from backend.migrate.__main__ import _tables, build_target
from common.db import RoutingRepository, load_flags, write_op
from common.db.marker import SCOPE_GROUP, SCOPE_SERVICE, migration_verified
from common.db.migrate import Runner
from common.db.migrate.cli import build_parser, run


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


async def add_origins(*origins):
    mongo = AllowedOriginsRepository()
    return [await mongo.add(o) for o in origins]


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
        if twin is None:
            continue
        cls = twin.args[0]
        rows = [cls.row, *getattr(cls, "document_rows", {}).values()]
        for row in rows:
            assert (
                COLLECTION_GROUPS[row.mongo_collection()] == group
            ), f"{name}: {row.__tablename__} is in group {group!r}"
            checked += 1
    assert checked > 30


# -- the marker ---------------------------------------------------------------
async def test_backfill_never_writes_and_a_clean_full_verify_writes_the_marker(target):
    await add_origins("https://a.example", "https://b.example")
    async with Runner(target) as runner:
        await runner.backfill()
        assert await marker_rows() == []
        reports = await runner.verify()
        outcome = await runner.record_verify(reports)
    assert outcome["marker"] == "written" and outcome["groups"] == list(GROUPS)
    marker = await current_marker()
    assert marker is not None and not marker.combined
    assert marker.collections["allowed_origins"] == {
        "group": "refdata",
        "mongo": 2,
        "postgres": 2,
    }
    assert set(marker.collections) == set(_tables())
    assert "+schema.0019" in marker.code_version
    assert marker.run_id == runner.run_id
    rows = await marker_rows()
    assert sorted(r["scope"] for r in rows) == [SCOPE_GROUP] * len(GROUPS) + [
        SCOPE_SERVICE
    ]


async def test_a_dirty_group_blocks_the_marker_until_reconciled(target):
    await add_origins("https://a.example")
    async with Runner(target) as runner:
        await runner.backfill()
    # written to Mongo only, after the backfill: missing in Postgres
    await WorkspaceDocument(title="W", workspace_name="w1", owner_id="o").save()
    async with Runner(target) as runner:
        outcome = await runner.record_verify(await runner.verify())
        assert "identity" not in outcome["groups"] and "refdata" in outcome["groups"]
        assert outcome["marker"] is None
        assert await current_marker() is None
        await runner.reconcile(["workspaces"])
        outcome = await runner.record_verify(await runner.verify())
    assert outcome["marker"] == "written"
    assert (await current_marker()).collections["workspaces"]["postgres"] == 1


async def test_sampled_and_collection_subset_verifies_are_not_recorded(target):
    async with Runner(target) as runner:
        reports = await runner.verify(sample_every=2)
        assert (await runner.record_verify(reports, sample_every=2))["reason"]
        reports = await runner.verify(["allowed_origins"])
        assert (await runner.record_verify(reports, subset=True))["reason"]
    assert await marker_rows() == []


async def test_per_group_verifies_combine_into_the_marker(target):
    await add_origins("https://a.example")
    async with Runner(target) as runner:
        await runner.backfill()
    outcomes = []
    for group in GROUPS:
        async with Runner(target) as runner:
            outcomes.append(
                await runner.record_verify(await runner.verify(collections_of(group)))
            )
    assert [o["groups"] for o in outcomes] == [[g] for g in GROUPS]
    assert [o["marker"] for o in outcomes] == [None] * (len(GROUPS) - 1) + ["combined"]
    marker = await current_marker()
    assert marker.combined and [b["group"] for b in marker.based_on] == list(GROUPS)
    group_rows = [r for r in await marker_rows() if r["scope"] == SCOPE_GROUP]
    assert marker.verified_at == min(r["verified_at"] for r in group_rows)
    assert marker.collections["allowed_origins"]["mongo"] == 1


async def test_a_backfill_after_a_group_verify_keeps_it_out_of_the_combination(
    target,
):
    await add_origins("https://a.example")
    async with Runner(target) as runner:
        await runner.backfill()
    first, *rest = GROUPS
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
async def test_reconcile_does_not_propagate_a_postgres_delete(target):
    """Under postgres_primary_dual a delete whose Mongo mirror failed leaves the
    document in Mongo and an outbox row in Postgres. ``reconcile --direction
    postgres->mongo`` copies rows to Mongo but never deletes: the document
    stays, verify keeps reporting it, and the outbox row is marked resolved
    anyway. Reconciling the other way (Mongo authoritative) resurrects it."""
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
        assert before.missing_in_postgres == 1
        # the kept row agrees: its replay stored the row's document exactly
        assert before.mismatched == 0
        result = await runner.reconcile(direction="postgres->mongo")
        assert result["allowed_origins"]["fixed"] == 0
        (after,) = await runner.verify(["allowed_origins"])
    assert await AllowedOriginsDocument.get(gone.id) is not None  # not deleted
    assert after.missing_in_postgres == 1 and after.mismatched == 0
    assert not after.clean
    async with container.pg_engine().connect() as conn:
        resolved = (await conn.execute(select(MirrorWriteFailure.resolved_at))).all()
    assert all(r[0] is not None for r in resolved)  # drained regardless

    async with Runner(target) as runner:
        await runner.reconcile(["allowed_origins"], direction="mongo->postgres")
        (back,) = await runner.verify(["allowed_origins"])
    assert back.clean  # the deleted row is back in Postgres


async def test_a_partial_reconcile_leaves_the_outbox_alone(target):
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name="WorkspaceRepository", row_id="x", op="save", error="E"
            )
        )
    async with Runner(target) as runner:
        await runner.reconcile(["allowed_origins"])
        assert (await runner.status())["outbox"]["postgres"] == 1
        await runner.reconcile()
        assert (await runner.status())["outbox"]["postgres"] == 0


# -- the CLI ------------------------------------------------------------------
def _args(*argv):
    return build_parser("python -m backend.migrate").parse_args(list(argv))


async def test_cli_group_verify_records_the_group_and_status_json(target, capsys):
    await add_origins("https://a.example")
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name="CouponRepository", row_id="x", op="add", error="E"
            )
        )
    assert await run(_args("--group", "refdata", "backfill"), target) == 0
    assert await run(_args("--group", "refdata", "verify"), target) == 0
    capsys.readouterr()
    rows = await marker_rows()
    assert [(r["scope"], r["groups"]) for r in rows] == [(SCOPE_GROUP, ["refdata"])]

    assert await run(_args("status", "--json"), target) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["format"] == 1 and report["service"] == "backend"
    assert report["collections"]["allowed_origins"] == {
        "group": "refdata",
        "mongo": 1,
        "postgres": 1,
        "backfill": report["collections"]["allowed_origins"]["backfill"],
    }
    assert report["collections"]["allowed_origins"]["backfill"]["state"] == "done"
    assert report["groups"]["refdata"]["last_verify"]["run_id"] == rows[0]["run_id"]
    assert report["groups"]["forms"]["last_verify"] is None
    assert report["last_verify"]["scope"] == SCOPE_GROUP
    assert report["marker"] is None
    assert report["outbox"] == {"mongo": 0, "postgres": 1}
    assert report["mirror_failures"]["postgres"] == {
        "total": 1,
        "unresolved": 1,
        "unresolved_by_method": {"CouponRepository.add": 1},
    }
    assert report["mirror_failures"]["mongo"]["unresolved"] == 0

    assert await run(_args("--group", "refdata", "status"), target) == 0
    text = capsys.readouterr().out
    assert "group refdata: last clean verify" in text and "group forms" not in text


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
