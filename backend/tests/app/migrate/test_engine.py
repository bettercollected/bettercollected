"""The migration CLI against both real stores: backfill copies Mongo documents
into rows it never lets clobber the application's own rows, verify sees the
truth, reconcile restores it, and a run resumes from its checkpoint.
Skipped unless DATABASE_URL points at a *_test database."""

import os

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select, text

from backend.app.container import container
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.postgres.refdata import PostgresAllowedOriginsRepository
from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.models import AllowedOriginRow, MigrationProgress, WorkspaceRow
from backend.migrate.__main__ import _tables
from common.db.base import SOURCE_APP, SOURCE_BACKFILL
from common.db.migrate import Runner, Target


@pytest.fixture
def target(clean_postgres):
    return Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=os.environ["DATABASE_URL"],
    )


async def rows(table):
    async with container.pg_engine().connect() as conn:
        return {r.id: r for r in (await conn.execute(select(table))).all()}


async def test_backfill_verify_reconcile_round_trip(target):
    mongo = AllowedOriginsRepository()
    for origin in ("https://a.example", "https://b.example", "https://c.example"):
        await mongo.add(origin)
    ws = WorkspaceDocument(title="W", workspace_name="w1", owner_id="o")
    await ws.save()
    # one row the application already dual-wrote: backfill must leave it alone
    app_written = await PostgresAllowedOriginsRepository(
        container.pg_sessionmaker()
    ).add("https://app.example")
    await AllowedOriginsDocument(
        id=app_written.id, origin="https://changed-in-mongo.example"
    ).save()

    async with Runner(target) as runner:
        pre = {
            r.collection: r
            for r in await runner.preflight(["allowed_origins", "workspaces"])
        }
        assert (pre["allowed_origins"].mongo, pre["allowed_origins"].postgres) == (4, 1)
        assert (
            pre["workspaces"].duplicates == 0
            and pre["allowed_origins"].invalid_ids == 0
        )

        result = await runner.backfill(["allowed_origins", "workspaces"])
        assert (
            result["allowed_origins"]["state"] == "done"
            and result["allowed_origins"]["count"] == 4
        )
        assert result["workspaces"]["count"] == 1
    origins = await rows(AllowedOriginRow)
    assert len(origins) == 4
    assert origins[str(app_written.id)]._bc_source == SOURCE_APP
    assert (
        origins[str(app_written.id)].doc["origin"] == "https://app.example"
    )  # not clobbered
    assert all(
        r._bc_source == SOURCE_BACKFILL
        for oid, r in origins.items()
        if oid != str(app_written.id)
    )
    assert (await rows(WorkspaceRow))[str(ws.id)].doc["workspace_name"] == "w1"

    async with Runner(target) as runner:
        reports = {
            r.collection: r
            for r in await runner.verify(["allowed_origins", "workspaces"])
        }
    assert reports["workspaces"].clean
    assert (
        reports["allowed_origins"].mismatched == 1
    )  # the app row Mongo disagrees with
    assert reports["allowed_origins"].samples["mismatched"] == [str(app_written.id)]

    # Mongo is authoritative in Phase 1: reconcile brings the row in line
    async with Runner(target) as runner:
        fixed = await runner.reconcile(["allowed_origins"])
        assert fixed["allowed_origins"]["fixed"] == 1
        assert all(r.clean for r in await runner.verify(["allowed_origins"]))
        status = await runner.status()
    assert status["collections"]["allowed_origins"]["state"] == "done"
    assert status["outbox"] == {"mongo": 0, "postgres": 0}
    assert (await rows(AllowedOriginRow))[str(app_written.id)].doc[
        "origin"
    ] == "https://changed-in-mongo.example"


async def test_backfill_resumes_from_its_checkpoint_and_dry_run_writes_nothing(target):
    mongo = AllowedOriginsRepository()
    for i in range(60):
        await mongo.add(f"https://{i}.example")
    async with Runner(target) as runner:
        assert (await runner.backfill(["allowed_origins"], dry_run=True))[
            "allowed_origins"
        ]["count"] == 60
        assert await rows(AllowedOriginRow) == {}
        first = await runner.backfill(["allowed_origins"], max_batches=1, batch_size=25)
        assert (
            first["allowed_origins"]["state"] == "paused"
            and 0 < first["allowed_origins"]["count"] < 60
        )
        checkpoint = (await runner.status())["collections"]["allowed_origins"]
        assert checkpoint["state"] == "paused" and checkpoint["last_id"]
        second = await runner.backfill(["allowed_origins"])
        assert (
            second["allowed_origins"]["state"] == "done"
            and second["allowed_origins"]["count"] == 60
        )
        assert (await runner.backfill(["allowed_origins"]))["allowed_origins"][
            "note"
        ] == "already done"
    assert len(await rows(AllowedOriginRow)) == 60


async def test_verify_reports_rows_mongo_no_longer_has(target):
    postgres = PostgresAllowedOriginsRepository(container.pg_sessionmaker())
    orphan = await postgres.add("https://only-in-postgres.example")
    async with Runner(target) as runner:
        (report,) = await runner.verify(["allowed_origins"])
        assert (
            report.missing_in_mongo == 1 and report.postgres == 1 and report.mongo == 0
        )
        # postgres->mongo puts it back (the R2/R3 fallback direction)
        await runner.reconcile(["allowed_origins"], direction="postgres->mongo")
    assert await AllowedOriginsDocument.get(orphan.id) is not None
