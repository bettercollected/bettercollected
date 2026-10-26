"""Two behaviours of the import engine that hold only against a concurrent
writer, ported from the dual-run mirror-order tests (the routing layer they
raced is gone; the engine's own guards are not):

* ``reconcile`` copies from one store to the other and must not overwrite a copy
  the application changed after reconcile read it (the conditional apply);
* a clean full ``verify`` resolves the unverified-copy outbox entries a 4.0
  mirror recorded (``CopyUnverified``), but only those recorded before that
  verify started.

The application's own write is played by hand: Postgres through the real forms
repository, Mongo with the frozen 4.0 Beanie class (tests/app/db/beanie_originals.py).
Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt
import os

import pytest
from sqlalchemy import select, update

from backend.app.container import container
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.models import FormRow, MigrationProgress, MirrorWriteFailure
from backend.migrate.__main__ import _tables
from backend.migrate.__main__ import build_target as backend_target
from common.db.canonical import checksum, from_canonical_document
from common.db.migrate import Runner, Target
from common.db.migrate.engine import UNVERIFIED_ERROR
from common.ids import RecordId
from common.models.standard_form import StandardForm
from tests.app.db.beanie_originals import FormDocument

UTC = dt.timezone.utc


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


async def new_form(title="Draft"):
    """A form both stores hold, as a mirrored 4.0 write left it."""
    created = await container.form_repo().create_form(
        StandardForm(form_id=str(RecordId()), title=title, builder_version="v2")
    )
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(select(FormRow.doc).where(FormRow.id == str(created.id)))
        ).scalar_one()
    await FormDocument.model_validate(from_canonical_document(doc)).insert()
    return created


async def set_postgres_title(form_id, title):
    """Change the Postgres copy behind the application's back (its updated_at
    stays: the application did not write it)."""
    table = FormRow.__table__
    async with container.pg_sessionmaker()() as session, session.begin():
        doc = (
            await session.execute(select(table.c.doc).where(table.c.id == str(form_id)))
        ).scalar_one()
        doc = {**doc, "title": title}
        await session.execute(
            update(table)
            .where(table.c.id == str(form_id))
            .values(doc=doc, _bc_checksum=checksum(doc))
        )


async def both_copies(form_id):
    """(Mongo's raw document, Postgres' doc) of the draft ``form_id``."""
    mongo = await FormDocument.get_pymongo_collection().find_one({"form_id": form_id})
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(select(FormRow.doc).where(FormRow.form_id == form_id))
        ).scalar_one_or_none()
    return mongo, doc


async def verify(target, *collections):
    async with Runner(target) as runner:
        reports = await runner.verify(list(collections))
    return {r.collection: r.as_dict() for r in reports if not r.clean}


class Interleaved(Runner):
    """A reconcile run that lets ``between`` (a write by the application)
    run once, after reading both stores and before its first write."""

    between = None

    async def _run_between_once(self):
        between, type(self).between = type(self).between, None
        if between is not None:
            await between()

    async def _apply_to_postgres(self, table, writes):
        await self._run_between_once()
        return await super()._apply_to_postgres(table, writes)

    async def _apply_to_mongo(self, coll, table, document, read, row_checksum):
        await self._run_between_once()
        return await super()._apply_to_mongo(coll, table, document, read, row_checksum)


@pytest.mark.parametrize(
    "stale, direction",
    [("postgres", "mongo->postgres"), ("mongo", "postgres->mongo")],
)
async def test_reconcile_never_overwrites_a_copy_changed_after_it_read_it(
    target, stale, direction
):
    """Reconcile reads both stores, the application then writes the document in
    both, and reconcile's copy, now older, must not land."""
    created = await new_form()
    # the other store's copy is stale, as after a failed mirror write
    if stale == "postgres":
        await set_postgres_title(created.id, "Stale")
    else:
        await FormDocument.get_pymongo_collection().update_one(
            {"_id": created.id}, {"$set": {"title": "Stale"}}
        )
    assert (await verify(target, "forms"))["forms"]["mismatched"] == 1

    async def application_write():
        stored = await container.form_repo().get_form_document_by_id(created.form_id)
        stored.title = "Newer"
        await container.form_repo().save_form(stored)  # Postgres, touches updated_at
        mongo_copy = await FormDocument.get_pymongo_collection().find_one({"_id": created.id})
        document = FormDocument.model_validate(
            {**{k: v for k, v in mongo_copy.items() if k != "_id"}, "id": created.id}
        )
        document.title = "Newer"
        document.updated_at = stored.updated_at
        await document.save()

    Interleaved.between = application_write
    async with Interleaved(target) as runner:
        result = await runner.reconcile(["forms"], direction=direction)

    assert result["forms"]["skipped"] == 1
    mongo, doc = await both_copies(created.form_id)
    assert mongo["title"] == doc["title"] == "Newer"


# -- unverified copies --------------------------------------------------------
async def mongo_entry(target, row_id, created_at):
    from pymongo import AsyncMongoClient

    client = AsyncMongoClient(target.mongo_uri, tz_aware=True)
    try:
        await client[target.mongo_db]["mirror_write_failures"].insert_one(
            {
                "table_name": "FormRepository",
                "row_id": row_id,
                "op": "save_form",
                "error": UNVERIFIED_ERROR + " forms: test",
                "attempts": 0,
                "resolved_at": None,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    finally:
        await client.close()


async def postgres_entry(row_id, created_at):
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            MirrorWriteFailure(
                table_name="FormRepository",
                row_id=row_id,
                op="save_form",
                error=UNVERIFIED_ERROR + " forms: test",
                created_at=created_at,
            )
        )


async def open_entries(target):
    from pymongo import AsyncMongoClient

    async with container.pg_sessionmaker()() as session:
        postgres = (
            await session.execute(
                select(MirrorWriteFailure.row_id).where(MirrorWriteFailure.resolved_at.is_(None))
            )
        ).scalars().all()
    client = AsyncMongoClient(target.mongo_uri, tz_aware=True)
    try:
        mongo = [
            d["row_id"]
            async for d in client[target.mongo_db]["mirror_write_failures"].find(
                {"resolved_at": None}
            )
        ]
    finally:
        await client.close()
    return sorted(postgres), sorted(mongo)


async def test_a_clean_verify_resolves_only_unverified_copies_recorded_before_it(
    target,
):
    """The stores agree after a clean full verify, so the copies a 4.0 mirror
    could not re-check (``CopyUnverified``) are fine: those recorded before the
    verify started are resolved, one recorded while it ran may concern a copy it
    read before the copy landed and stays open."""
    target = backend_target(os.environ["DATABASE_URL"])
    now = dt.datetime.now(UTC)
    earlier, later = now - dt.timedelta(minutes=5), now + dt.timedelta(minutes=5)
    await mongo_entry(target, "before", earlier)
    await postgres_entry("before", earlier)
    async with Runner(target) as runner:
        reports = await runner.verify()
        # recorded while that verify ran
        await mongo_entry(target, "during", later)
        await postgres_entry("during", later)
        outcome = await runner.record_verify(reports)
    assert outcome["marker"] == "written"
    assert await open_entries(target) == (["during"], ["during"])
