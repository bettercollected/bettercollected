"""Deletes leave tombstones, and verify and reconcile honour them.

A record a 4.0 stack deleted in one store whose mirror delete failed survives
in the other. ``reconcile`` never copies such a survivor: it deletes it, in
both directions, and never copies a deleted record. The stacks' two stores are
planted here by hand: Postgres through the real repositories (a delete records
its tombstone in the same transaction), Mongo with the frozen 4.0 classes
(tests/app/db/beanie_originals.py) and the tombstone document a 4.0 Mongo
delete recorded. Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt
import os

import pytest
from common.ids import RecordId
from sqlalchemy import select

from backend.app.container import container
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.models import DeletionTombstone, FormRow, MigrationProgress
from backend.migrate.__main__ import _tables
from common.db import tombstones
from common.db.canonical import from_canonical_document
from common.db.migrate import Runner, Target
from common.models.standard_form import StandardForm
from tests.app.db.beanie_originals import FormDocument


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


def forms_repo():
    return container.form_repo()


async def new_form(title="Draft", *, mongo=True, postgres=True):
    """A form as a stack that mirrored its writes left it: in the stores
    asked for, the same document (id, stamps, bytes) in each."""
    created = await forms_repo().create_form(
        StandardForm(form_id=str(RecordId()), title=title, builder_version="v2")
    )
    if mongo:
        await mongo_insert_copy(created.id)
    if not postgres:
        async with container.pg_sessionmaker()() as session, session.begin():
            await session.execute(FormRow.__table__.delete().where(FormRow.id == str(created.id)))
    return created


async def mongo_insert_copy(document_id):
    """Mongo's copy of the Postgres row ``document_id``, as 4.0 stored it."""
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(
                select(FormRow.doc).where(FormRow.id == str(document_id))
            )
        ).scalar_one()
    await FormDocument.model_validate(from_canonical_document(doc)).insert()


async def mongo_delete(document_id):
    """A 4.0 Mongo delete: the document goes, its tombstone is recorded."""
    collection = FormDocument.get_pymongo_collection()
    await collection.delete_one({"_id": document_id})
    await collection.database[tombstones.COLLECTION].insert_one(
        {
            "_id": f"forms:{document_id}",
            "collection": "forms",
            "row_id": str(document_id),
            "deleted_at": tombstones.to_ms(dt.datetime.now(dt.timezone.utc)),
        }
    )


async def postgres_tombstones():
    async with container.pg_sessionmaker()() as session:
        rows = (await session.execute(select(DeletionTombstone))).scalars().all()
    return {(r.collection, r.row_id) for r in rows}


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


async def test_a_delete_records_a_tombstone_with_ids_and_times_only(target):
    created = await new_form(mongo=False)
    await forms_repo().delete_form(created.form_id)

    assert ("forms", str(created.id)) in await postgres_tombstones()
    async with container.pg_sessionmaker()() as session:
        (tombstone,) = (await session.execute(select(DeletionTombstone))).scalars().all()
    # ids and times only: no document content
    assert {c.name for c in DeletionTombstone.__table__.columns} == {
        "collection",
        "row_id",
        "deleted_at",
    }
    assert tombstone.deleted_at is not None


async def test_a_bulk_delete_records_every_id(target):
    forms = [await new_form(f"Form {i}", mongo=False) for i in range(3)]
    kept = await new_form("Kept")
    await forms_repo().delete_forms([f.form_id for f in forms])

    assert await postgres_tombstones() == {("forms", str(f.id)) for f in forms}
    assert await copies(kept.id) == (True, True)


@pytest.mark.parametrize(
    "deleted_in, direction",
    [
        ("mongo", "mongo->postgres"),
        ("mongo", "postgres->mongo"),
        ("postgres", "mongo->postgres"),
        ("postgres", "postgres->mongo"),
    ],
)
async def test_a_failed_mirror_delete_is_completed_by_reconcile_in_either_direction(
    target, deleted_in, direction
):
    """A 4.0 stack deleted a form in one store (a tombstone there) and the
    delete never reached the other: the copy left is a deleted record."""
    created = await new_form()
    kept = await new_form("Kept")
    if deleted_in == "mongo":
        await mongo_delete(created.id)
    else:
        await forms_repo().delete_form(created.form_id)

    survivor = (False, True) if deleted_in == "mongo" else (True, False)
    assert await copies(created.id) == survivor
    report = await verify(target)
    assert report.tombstoned == 1 and not report.clean
    assert report.samples["tombstoned"] == [str(created.id)]

    result = await reconcile(target, direction)
    assert result["deleted"] == 1 and result["fixed"] == 0
    assert await copies(created.id) == (False, False)
    assert await copies(kept.id) == (True, True)
    assert (await verify(target)).clean


async def test_a_record_deleted_while_mongo_is_no_longer_written_is_not_brought_back(
    target,
):
    """Deleted in Postgres (Mongo keeps its old copy), then reconciled from
    Mongo: the copy goes."""
    created = await new_form()
    await forms_repo().delete_form(created.form_id)
    assert await copies(created.id) == (True, False)

    result = await reconcile(target, "mongo->postgres")
    assert result["deleted"] == 1
    assert await copies(created.id) == (False, False)


async def test_copies_on_both_sides_of_a_deleted_record_are_reported_not_deleted(
    target,
):
    """Both copies older than the delete (as after an earlier reconcile
    brought the record back): verify and reconcile report it."""
    created = await new_form()
    raw = await FormDocument.get_pymongo_collection().find_one({"_id": created.id})
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(
                select(FormRow.doc).where(FormRow.id == str(created.id))
            )
        ).scalar_one()
    await forms_repo().delete_form(created.form_id)
    await mongo_delete(created.id)
    # brought back on both sides as they were before the delete
    await FormDocument.get_pymongo_collection().insert_one(raw)
    await forms_repo().upsert(created.__class__.model_validate(from_canonical_document(doc)))
    assert await copies(created.id) == (True, True)

    assert (await verify(target)).tombstoned == 1
    result = await reconcile(target, "mongo->postgres")
    assert result["tombstoned"] == 1 and result["deleted"] == 0
    assert await copies(created.id) == (True, True)


async def test_a_record_written_again_after_its_delete_is_not_a_deleted_record(
    target,
):
    """A tombstone older than the copy (the id was written again after the
    delete, as relation-derived ids are) does not stop the copy."""
    created = await new_form()
    await forms_repo().delete_form(created.form_id)
    await mongo_delete(created.id)
    # Mongo's copy is written again, later than the delete
    document = from_row_doc_of(created)
    document.title = "Written again"
    document.updated_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1)
    await document.insert()
    assert await copies(created.id) == (True, False)

    report = await verify(target)
    assert report.tombstoned == 0 and report.missing_in_postgres == 1
    result = await reconcile(target, "mongo->postgres")
    assert result["fixed"] == 1 and result["deleted"] == 0
    assert await copies(created.id) == (True, True)


def from_row_doc_of(created):
    """The frozen Beanie form for the Record ``created`` (same id and stamps)."""
    return FormDocument.model_validate(created.model_dump(mode="json", by_alias=True))


async def test_reconcile_prunes_postgres_tombstones_past_their_retention(target):
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        days=tombstones.RETENTION_DAYS + 1
    )
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            DeletionTombstone(
                collection="forms", row_id=str(RecordId()), deleted_at=old
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


# -- review follow-ups -------------------------------------------------------


async def test_saving_a_groups_emails_again_deletes_nothing_for_good(target):
    """Saving a group's emails deletes and re-inserts its members in one
    write, under ids derived from (group, email): the same ids come back with
    the delete's own time, at microseconds in Postgres and milliseconds in
    Mongo. They are not deleted records."""
    groups = container.responder_groups_repository()
    workspace_id = RecordId()
    group = await groups.create_group(workspace_id, "Group")
    emails = ["a@example.com", "b@example.com"]
    await groups.add_emails_to_group(group.id, emails)
    await groups.update_group(workspace_id, emails=emails, group_id=group.id)
    await mirror_to_mongo("responder_group_member")

    async with Runner(target) as runner:
        (report,) = await runner.verify(["responder_group_member"])
        assert report.tombstoned == 0 and report.clean
        result = await runner.reconcile(
            ["responder_group_member"], direction="mongo->postgres"
        )
    assert result["responder_group_member"]["deleted"] == 0
    members = await groups.get_emails_in_group(group.id)
    assert sorted(members["emails"]) == emails


async def mirror_to_mongo(collection):
    """Every Postgres row of ``collection`` as a Mongo document, as 4.0's
    mirror left them (the stamps at Mongo's millisecond precision)."""
    from backend.db.base import Base

    row = next(
        m.class_
        for m in Base.registry.mappers
        if hasattr(m.class_, "mongo_collection")
        and m.class_.mongo_collection() == collection
    )
    async with container.pg_sessionmaker()() as session:
        docs = (await session.execute(select(row.doc))).scalars().all()
    database = FormDocument.get_pymongo_collection().database
    for doc in docs:
        await database[collection].insert_one(from_canonical_document(doc))


class DeleteBetween(Runner):
    """A reconcile run during which the application deletes a record: after
    the run has collected the deleted records, before it copies."""

    between = None

    async def _reconcile_collection(self, *args, **kwargs):
        between, type(self).between = type(self).between, None
        if between is not None:
            await between()
        return await super()._reconcile_collection(*args, **kwargs)


async def test_a_delete_racing_reconcile_is_not_copied_back(target):
    """Postgres deletes while its Mongo mirror fails, after reconcile looked
    for deleted records: the copy from Mongo must not re-insert it (the insert
    checks for a newer tombstone)."""
    created = await new_form()
    other = await new_form("Other")
    # something for reconcile to do, so it walks the collection
    await FormDocument.get_pymongo_collection().update_one(
        {"_id": other.id}, {"$set": {"title": "Stale"}}
    )

    async def application_delete():
        await forms_repo().delete_form(created.form_id)

    DeleteBetween.between = application_delete
    async with DeleteBetween(target) as runner:
        result = await runner.reconcile(["forms"], direction="mongo->postgres")
    assert await copies(created.id) == (True, False)  # not re-inserted
    assert result["forms"]["skipped"] == 1

    # the next verify names it, and the next reconcile removes the stray copy
    assert (await verify(target)).tombstoned == 1
    assert (await reconcile(target, "mongo->postgres"))["deleted"] == 1
    assert await copies(created.id) == (False, False)


async def test_reconcile_never_copies_an_expired_ttl_record(target):
    """Mongo's TTL index removes an expired counter on its own schedule and
    the twin drops it when it counts; reconcile must not copy it back."""
    # a 4.0 Mongo: the collection and its TTL index (no Beanie class any more)
    counters = FormDocument.get_pymongo_collection().database["rate_limit_counters"]
    await counters.create_index("expires_at", expireAfterSeconds=0)
    now = dt.datetime.now(dt.timezone.utc)
    await counters.insert_one(
        {
            "_id": RecordId(),
            "hits": 1,
            "expires_at": now - dt.timedelta(minutes=5),
            "created_at": now - dt.timedelta(hours=1),
            "updated_at": now - dt.timedelta(hours=1),
        }
    )
    async with Runner(target) as runner:
        result = await runner.reconcile(
            ["rate_limit_counters"], direction="mongo->postgres"
        )
    assert result["rate_limit_counters"]["fixed"] == 0


async def test_a_record_written_again_in_the_deleting_write_is_not_deleted(target):
    """One write deletes a record and writes it again under the same id, so
    the tombstone and both copies carry the same clock reading: microseconds
    in Postgres, milliseconds where Mongo stores a BSON date. Compared at
    millisecond precision, neither copy is a deleted record."""
    from backend.db.models import AllowedOriginRow
    from common.db.canonical import canonical_document, checksum

    at = dt.datetime(2026, 10, 24, 12, 0, 0, 123456, tzinfo=dt.timezone.utc)
    document = {
        "_id": RecordId(),
        "origin": "https://again.example",
        "created_at": at.replace(microsecond=123000),
        "updated_at": at.replace(microsecond=123000),  # Mongo keeps milliseconds
    }
    await FormDocument.get_pymongo_collection().database["allowed_origins"].insert_one(
        dict(document)
    )
    doc = canonical_document(document)
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(
            AllowedOriginRow(
                id=str(document["_id"]),
                doc=doc,
                created_at=at,
                updated_at=at,  # Postgres keeps microseconds
                bc_checksum=checksum(doc),
            )
        )
        session.add(
            DeletionTombstone(
                collection="allowed_origins", row_id=str(document["_id"]), deleted_at=at
            )
        )

    async with Runner(target) as runner:
        (report,) = await runner.verify(["allowed_origins"])
    assert report.tombstoned == 0


async def test_deletes_prune_expired_postgres_tombstones_as_they_go(
    target, monkeypatch
):
    """Not only reconcile prunes: a service drops expired tombstones while it
    records deletes, so the table stays bounded."""
    monkeypatch.setattr(tombstones, "PRUNE_EVERY", 1)
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        days=tombstones.RETENTION_DAYS + 1
    )
    async with container.pg_sessionmaker()() as session, session.begin():
        session.add(DeletionTombstone(collection="forms", row_id="old", deleted_at=old))
    created = await new_form(mongo=False)
    await forms_repo().delete_form(created.form_id)
    assert await postgres_tombstones() == {("forms", str(created.id))}


class DeleteBeforeInsert(Runner):
    """A reconcile run where the application deletes the record after the
    run checked the row and before its Mongo insert lands."""

    between = None

    async def _insert_copy(self, coll, document):
        between, type(self).between = type(self).between, None
        if between is not None:
            await between()
        await coll.insert_one(document)


async def test_a_delete_landing_before_the_mongo_insert_is_not_brought_back(target):
    """postgres->mongo: the row is checked, then deleted (Postgres, with its
    tombstone), then the copy lands in Mongo."""
    created = await new_form(mongo=False)
    # Mongo lacks the document (not deleted: e.g. a mirror insert that failed)

    async def application_delete():
        await forms_repo().delete_form(created.form_id)

    DeleteBeforeInsert.between = application_delete
    async with DeleteBeforeInsert(target) as runner:
        result = await runner.reconcile(["forms"], direction="postgres->mongo")
    assert result["forms"]["fixed"] == 0 and result["forms"]["skipped"] == 1
    assert await copies(created.id) == (False, False)
    assert (await verify(target)).clean


async def test_pruning_runs_outside_the_delete_and_never_undoes_it(target, monkeypatch):
    """Pruning happens after the delete committed, in a transaction of its
    own: a prune that fails leaves the delete and its tombstone in place."""
    import common.records.repository as record_repository

    monkeypatch.setattr(tombstones, "PRUNE_EVERY", 1)
    calls = []

    async def failing_prune(session, schema, now=None):
        calls.append(schema)
        raise RuntimeError("prune failed")

    monkeypatch.setattr(record_repository, "prune_postgres", failing_prune)
    created = await new_form(mongo=False)
    await forms_repo().delete_form(created.form_id)

    assert calls == ["app"]
    assert await copies(created.id) == (False, False)
    assert await postgres_tombstones() == {("forms", str(created.id))}
