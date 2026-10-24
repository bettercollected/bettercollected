"""Deletes leave tombstones, and verify and reconcile honour them.

A record deleted in one store whose mirror delete failed survives in the
other. ``reconcile`` used to copy such a survivor back in one direction; it
now deletes it instead, in both directions, and never copies a deleted record.
The write modes are set on the repositories built here, whatever mode the
suite runs in. Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt
import functools
import os

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.postgres.forms import PostgresFormRepository
from backend.app.schemas.standard_form import FormDocument
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.models import DeletionTombstone, FormRow, MigrationProgress
from backend.migrate.__main__ import _tables
from common.db import ReadSource, RoutingRepository, load_flags
from common.db import tombstones
from common.db.canonical import from_canonical_document
from common.db.migrate import Runner, Target
from common.models.standard_form import StandardForm

READ = {
    "mongo": "mongo",
    "dual": "mongo",
    "postgres_primary_dual": "postgres",
    "postgres": "postgres",
}


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


class Down:
    """``store`` while it is unreachable: every call fails."""

    def __init__(self, store):
        self._store = store

    async def replay_write(self, documents):
        raise ConnectionError("store unreachable")

    def __getattr__(self, name):
        @functools.wraps(getattr(self._store, name))
        async def fail(*args, **kwargs):
            raise ConnectionError("store unreachable")

        return fail


def forms_repo(mode, *, mirror_down=False):
    flags = load_flags({"DB_WRITE_MODE": mode, "DB_READ_SOURCE": READ[mode]})
    mongo = FormRepository()
    postgres = PostgresFormRepository(
        container.pg_sessionmaker(),
        container.responder_groups_repository(),
        container.form_response_repo(),
    )
    if mirror_down:
        if flags.mirror_store("forms") is ReadSource.POSTGRES:
            postgres = Down(postgres)
        else:
            mongo = Down(mongo)
    return RoutingRepository(
        group="forms",
        flags=flags,
        mongo=mongo,
        postgres=postgres,
        on_mirror_failure=container.outbox_recorder(),
    )


async def new_form(repo, title="Draft"):
    return await repo.create_form(
        StandardForm(form_id=str(PydanticObjectId()), title=title, builder_version="v2")
    )


async def postgres_tombstones():
    async with container.pg_sessionmaker()() as session:
        rows = (await session.execute(select(DeletionTombstone))).scalars().all()
    return {(r.collection, r.row_id) for r in rows}


async def mongo_tombstones():
    found = await (
        FormDocument.get_pymongo_collection()
        .database[tombstones.COLLECTION]
        .find({})
        .to_list()
    )
    return {(d["collection"], d["row_id"]) for d in found}, found


async def copies(document_id):
    """(in Mongo, in Postgres) for the forms document ``document_id``."""
    mongo = await FormDocument.get_pymongo_collection().find_one({"_id": document_id})
    async with container.pg_sessionmaker()() as session:
        row = await session.get(FormRow, str(document_id))
    return mongo is not None, row is not None


async def verify(target):
    async with Runner(target) as runner:
        return (await runner.verify(["forms"]))[0]


async def reconcile(target, direction):
    async with Runner(target) as runner:
        return (await runner.reconcile(["forms"], direction=direction))["forms"]


@pytest.mark.parametrize(
    "mode, mongo_records, postgres_records",
    [
        ("mongo", True, False),
        ("dual", True, True),
        ("postgres_primary_dual", True, True),
        ("postgres", False, True),
    ],
)
async def test_a_delete_records_a_tombstone_in_each_store_that_deletes(
    target, mode, mongo_records, postgres_records
):
    repo = forms_repo(mode)
    created = await new_form(repo)
    await repo.delete_form(created.form_id)

    key = ("forms", str(created.id))
    in_mongo, documents = await mongo_tombstones()
    assert (key in in_mongo) is mongo_records
    assert (key in await postgres_tombstones()) is postgres_records
    # ids and times only: no document content
    for document in documents:
        assert set(document) == {"_id", "collection", "row_id", "deleted_at"}


async def test_a_bulk_delete_records_every_id(target):
    repo = forms_repo("dual")
    forms = [await new_form(repo, f"Form {i}") for i in range(3)]
    kept = await new_form(repo, "Kept")
    await repo.delete_forms([f.form_id for f in forms])

    deleted = {("forms", str(f.id)) for f in forms}
    assert (await mongo_tombstones())[0] == deleted
    assert await postgres_tombstones() == deleted
    assert await copies(kept.id) == (True, True)


@pytest.mark.allow_mirror_failures
@pytest.mark.parametrize(
    "mode, direction",
    [
        ("dual", "mongo->postgres"),
        ("dual", "postgres->mongo"),
        ("postgres_primary_dual", "mongo->postgres"),
        ("postgres_primary_dual", "postgres->mongo"),
    ],
)
async def test_a_failed_mirror_delete_is_completed_by_reconcile_in_either_direction(
    target, mode, direction
):
    healthy = forms_repo(mode)
    created = await new_form(healthy)
    kept = await new_form(healthy, "Kept")
    await forms_repo(mode, mirror_down=True).delete_form(created.form_id)

    survivor = (False, True) if mode == "dual" else (True, False)
    assert await copies(created.id) == survivor
    report = await verify(target)
    assert report.tombstoned == 1 and not report.clean
    assert report.samples["tombstoned"] == [str(created.id)]

    result = await reconcile(target, direction)
    assert result["deleted"] == 1 and result["fixed"] == 0
    assert await copies(created.id) == (False, False)
    assert await copies(kept.id) == (True, True)
    assert (await verify(target)).clean


@pytest.mark.allow_mirror_failures
async def test_a_record_deleted_while_mongo_is_no_longer_written_is_not_brought_back(
    target,
):
    """Deleted under ``postgres`` (Mongo keeps its old copy), then rolled back
    to ``postgres_primary_dual`` and reconciled from Mongo: the copy goes."""
    created = await new_form(forms_repo("postgres_primary_dual"))
    await forms_repo("postgres").delete_form(created.form_id)
    assert await copies(created.id) == (True, False)

    result = await reconcile(target, "mongo->postgres")
    assert result["deleted"] == 1
    assert await copies(created.id) == (False, False)


async def test_copies_on_both_sides_of_a_deleted_record_are_reported_not_deleted(
    target,
):
    """Both copies older than the delete (as after an earlier reconcile
    brought the record back): verify and reconcile report it."""
    repo = forms_repo("dual")
    created = await new_form(repo)
    raw = await FormDocument.get_pymongo_collection().find_one({"_id": created.id})
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(
                select(FormRow.doc).where(FormRow.id == str(created.id))
            )
        ).scalar_one()
    await repo.delete_form(created.form_id)
    # brought back on both sides as they were before the delete
    await FormDocument.get_pymongo_collection().wrapped.insert_one(raw)
    await PostgresFormRepository(container.pg_sessionmaker(), None, None).upsert(
        FormDocument.model_validate(from_canonical_document(doc))
    )
    assert await copies(created.id) == (True, True)

    assert (await verify(target)).tombstoned == 1
    result = await reconcile(target, "mongo->postgres")
    assert result["tombstoned"] == 1 and result["deleted"] == 0
    assert await copies(created.id) == (True, True)


@pytest.mark.allow_mirror_failures
async def test_a_record_written_again_after_its_delete_is_not_a_deleted_record(
    target,
):
    """A tombstone older than the copy (the id was written again after the
    delete, as relation-derived ids are) does not stop the copy."""
    repo = forms_repo("dual")
    created = await new_form(repo)
    document = await repo.get_form_document_by_id(created.form_id)
    await repo.delete_form(created.form_id)
    document.title = "Written again"
    document.updated_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1)
    await forms_repo("dual", mirror_down=True).save_form(document)
    assert await copies(created.id) == (True, False)

    report = await verify(target)
    assert report.tombstoned == 0 and report.missing_in_postgres == 1
    result = await reconcile(target, "mongo->postgres")
    assert result["fixed"] == 1 and result["deleted"] == 0
    assert await copies(created.id) == (True, True)


async def test_reconcile_prunes_postgres_tombstones_past_their_retention(target):
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        days=tombstones.RETENTION_DAYS + 1
    )
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            DeletionTombstone(
                collection="forms", row_id=str(PydanticObjectId()), deleted_at=old
            )
        )
        session.add(
            DeletionTombstone(
                collection="forms",
                row_id="kept",
                deleted_at=dt.datetime.now(dt.timezone.utc),
            )
        )
    await reconcile(target, "mongo->postgres")
    assert await postgres_tombstones() == {("forms", "kept")}


async def test_mongo_tombstones_expire_by_a_ttl_index(target):
    indexes = await (
        FormDocument.get_pymongo_collection()
        .database[tombstones.COLLECTION]
        .index_information()
    )
    ttl = indexes["deleted_at_ttl"]
    assert ttl["expireAfterSeconds"] == tombstones.RETENTION_DAYS * 86400
