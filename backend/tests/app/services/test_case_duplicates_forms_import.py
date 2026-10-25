"""The case-duplicate accounts routes count forms in Postgres only (4.1):
until the forms import is complete (a finished backfill of workspace_forms
recorded, or every link of Mongo's 4.0 copy in Postgres) every account would
count none and the newest of each group would be kept, so both the plan and
a drop refuse with 409 ``forms_import_incomplete``, also while a configured
Mongo cannot be read. Without Mongo configured nothing is checked.

The tests that use the test Mongo are Mongo-driven (tests/conftest.py)."""

from contextlib import asynccontextmanager

import pytest
from beanie import PydanticObjectId
from pymongo import AsyncMongoClient
from sqlalchemy import delete, insert

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.case_duplicate_accounts import CaseDuplicateAccounts
from backend.config import settings
from backend.config.database import MongoSettings
from backend.db.models import MigrationProgress
from common.records import to_bson
from tests.conftest import TEST_MONGO_DB


def _link(workspace_id, form_id):
    return WorkspaceFormDocument(
        id=PydanticObjectId(), workspace_id=workspace_id, form_id=form_id, user_id="u1"
    )


def _opened(database):
    @asynccontextmanager
    async def opened():
        yield database

    return opened


def _service(**stores):
    service = CaseDuplicateAccounts(
        http_client=None,
        workspace_repo=container.workspace_repo(),
        workspace_form_repo=container.workspace_form_repo(),
        auth_service=None,
        **stores,
    )

    async def no_groups():  # the auth service is never asked first
        return []

    service._group_ids = no_groups
    return service


async def _refused(service):
    for call in (service.plan, lambda: service.drop(str(PydanticObjectId()))):
        with pytest.raises(HTTPException) as refused:
            await call()
        assert refused.value.status_code == 409
        assert refused.value.content["code"] == "forms_import_incomplete"
    return refused.value.content["message"]


async def _backfill_finished(last_id=None, skipped=0):
    table = MigrationProgress.__table__
    async with container.pg_engine().begin() as conn:
        await conn.execute(delete(table).where(table.c.collection == "workspace_forms"))
        await conn.execute(
            insert(table).values(
                collection="workspace_forms",
                count=2,
                skipped=skipped,
                batch_size=200,
                state="done",
                last_id=None if last_id is None else str(last_id),
            )
        )


@pytest.fixture
def mongo(clean_postgres):
    return container.database_client()[TEST_MONGO_DB]


async def test_the_plan_and_drops_wait_for_a_complete_forms_import(mongo):
    ws_a, ws_b = PydanticObjectId(), PydanticObjectId()
    imported, not_yet = _link(ws_a, "f1"), _link(ws_b, "f1")
    await container.workspace_form_repo().save(imported)
    await mongo["workspace_forms"].insert_many([to_bson(imported), to_bson(not_yet)])
    service = _service(mongo_database=_opened(mongo))

    message = await _refused(service)
    assert str(ws_b) not in message and "1 workspace link" in message  # counts only

    await container.workspace_form_repo().save(not_yet)
    assert await service.plan() == []
    assert await service.drop(str(PydanticObjectId())) == "not_found"


async def test_a_link_deleted_after_a_finished_import_does_not_block(mongo):
    """Since 4.1 a link is deleted in Postgres only, so it stays in Mongo's
    frozen copy: a finished backfill (the startup guard's signal too) counts
    as a complete import; without one the missing link still refuses."""
    deleted = _link(PydanticObjectId(), "f1")
    await mongo["workspace_forms"].insert_one(to_bson(deleted))
    service = _service(mongo_database=_opened(mongo))
    await _refused(service)

    await _backfill_finished(last_id=deleted.id)
    assert await service.plan() == []


async def test_a_link_written_to_mongo_after_a_finished_backfill_refuses(mongo):
    """4.0 wrote a link after the backfill finished (a rollback, a rehearsal
    on the same database): past the backfill's last copied id, so the import
    is incomplete again until a backfill copies it."""
    copied = _link(PydanticObjectId(), "f1")
    await container.workspace_form_repo().save(copied)
    await mongo["workspace_forms"].insert_one(to_bson(copied))
    await _backfill_finished(last_id=copied.id)
    service = _service(mongo_database=_opened(mongo))
    assert await service.plan() == []

    later = _link(PydanticObjectId(), "f2")  # a newer ObjectId
    await mongo["workspace_forms"].insert_one(to_bson(later))
    assert "1 workspace link" in await _refused(service)
    await _backfill_finished(last_id=later.id)  # the backfill ran again
    assert await service.plan() == []


async def test_a_backfill_that_skipped_documents_falls_back_to_the_links(mongo):
    missing = _link(PydanticObjectId(), "f1")
    await mongo["workspace_forms"].insert_one(to_bson(missing))
    await _backfill_finished(last_id=missing.id, skipped=1)
    service = _service(mongo_database=_opened(mongo))
    await _refused(service)  # not a complete import: the link is missing
    await container.workspace_form_repo().save(missing)
    assert await service.plan() == []


async def test_an_unreachable_mongo_refuses(clean_postgres):
    client = AsyncMongoClient(
        "mongodb://mongo-not-used.invalid/?serverSelectionTimeoutMS=300"
    )
    try:
        service = _service(mongo_database=_opened(client["bettercollected_backend"]))
        assert "Mongo could not be read" in await _refused(service)
    finally:
        await client.close()


async def test_default_settings_without_mongo_in_use_check_nothing(
    clean_postgres, monkeypatch
):
    """A fresh 4.1 install: ``MONGO_URI`` unset (only the built-in default)
    and no group on Mongo. The routes work: nothing to import."""
    if container.flags().uses_mongo(("responses",)):
        pytest.skip("a group of this run uses Mongo")
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.setattr(settings, "mongo_settings", MongoSettings())
    assert "URI" not in settings.mongo_settings.model_fields_set
    service = _service()  # the real Mongo and Postgres openers
    assert await service.plan() == []
    assert await service.drop(str(PydanticObjectId())) == "not_found"
