"""``set_form_logo`` through the routed forms repository, under ``dual``
(Mongo primary) and ``postgres_primary_dual`` (Postgres primary): both stores
get the logo and nothing else, and a draft one store lacks ends the same in
both instead of being re-created where it was deleted. Drives a Mongo server;
skipped unless DATABASE_URL points at a *_test database."""

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.postgres.forms import PostgresFormRepository
from backend.app.schemas.standard_form import FormDocument
from backend.db.models import FormRow
from common.db import RoutingRepository, load_flags

LOGO = "https://logo/new.png"
MODES = {
    "dual": {"DB_WRITE_MODE": "dual", "DB_READ_SOURCE": "mongo"},
    "postgres_primary_dual": {
        "DB_WRITE_MODE": "postgres_primary_dual",
        "DB_READ_SOURCE": "postgres",
    },
}


@pytest.fixture
def postgres(clean_postgres):
    return PostgresFormRepository(container.pg_sessionmaker(), None, None)


def routed(postgres, mode):
    return RoutingRepository(
        group="forms",
        flags=load_flags(MODES[mode]),
        mongo=FormRepository(),
        postgres=postgres,
        on_mirror_failure=container.outbox_recorder(),
    )


def draft() -> FormDocument:
    return FormDocument(
        id=PydanticObjectId(),
        form_id=str(PydanticObjectId()),
        title="Draft",
        builder_version="v2",
        logo="https://logo/old.png",
    )


async def postgres_copy(form_id):
    async with container.pg_sessionmaker()() as session:
        return (
            await session.execute(select(FormRow.doc).where(FormRow.form_id == form_id))
        ).scalar_one_or_none()


async def mongo_copy(form_id):
    return await FormDocument.get_pymongo_collection().find_one({"form_id": form_id})


async def stored_in_both(postgres, form: FormDocument) -> None:
    await routed(postgres, "dual").save_form(form)
    assert await postgres_copy(form.form_id) and await mongo_copy(form.form_id)


@pytest.mark.parametrize("mode", list(MODES))
async def test_both_stores_get_the_logo_and_keep_updated_at(postgres, mode):
    form = draft()
    await stored_in_both(postgres, form)
    before = await postgres_copy(form.form_id)

    await routed(postgres, mode).set_form_logo(form.form_id, LOGO)

    after = await postgres_copy(form.form_id)
    assert after["logo"] == LOGO
    assert after["updated_at"] == before["updated_at"]
    assert after["title"] == "Draft"
    assert (await mongo_copy(form.form_id))["logo"] == LOGO


async def test_dual_a_missing_postgres_copy_is_converged_from_mongo(postgres):
    form = draft()
    await form.save()  # Mongo only: the Postgres copy is missing
    assert await postgres_copy(form.form_id) is None

    await routed(postgres, "dual").set_form_logo(form.form_id, LOGO)

    copy = await postgres_copy(form.form_id)
    assert copy is not None
    assert copy["logo"] == LOGO and copy["title"] == "Draft"


async def test_postgres_primary_a_deleted_draft_is_not_re_created(postgres):
    form = draft()
    await form.save()  # a stale Mongo copy of a draft Postgres no longer holds
    assert await postgres_copy(form.form_id) is None

    result = await routed(postgres, "postgres_primary_dual").set_form_logo(
        form.form_id, LOGO
    )

    assert result is None
    assert await postgres_copy(form.form_id) is None
    # converged from the primary: the stale mirror copy is gone too
    assert await mongo_copy(form.form_id) is None
