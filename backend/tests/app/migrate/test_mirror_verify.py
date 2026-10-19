"""A write through a routed repository leaves both stores identical: ``verify``
is clean right after it, in both mixed write modes, without a reconcile.

``dual`` (Mongo primary, Postgres mirror) and ``postgres_primary_dual``
(Postgres primary, Mongo mirror) are set on the repositories built here,
whatever mode the suite runs in. The covered shapes: a replayed insert, a
re-executed save that stamps ``updated_at``, a replayed conditional update,
a counter created and bumped on both stores, documents with derived ids built
on both stores, and a mirror failure that the reconcile then repairs from the
outbox. Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt
import functools
import os

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.postgres.forms import PostgresFormRepository
from backend.app.repositories.postgres.refdata import PostgresAllowedOriginsRepository
from backend.app.repositories.postgres.ai import PostgresRateLimitRepository
from backend.app.repositories.postgres.responses import (
    PostgresResponderGroupsRepository,
)
from backend.app.repositories.rate_limit_repository import RateLimitRepository
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.models.template import StandardFormTemplate
from backend.app.schemas.standard_form import FormDocument
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.models import MigrationProgress
from backend.migrate.__main__ import _tables
from common.db import ReadSource, RoutingRepository, load_flags
from common.db.migrate import Runner, Target
from common.models.standard_form import StandardForm
from tests.app.controllers.data import testUser

MODES = ["dual", "postgres_primary_dual"]
# reconcile direction: from the primary to the mirror
DIRECTION = {"dual": "mongo->postgres", "postgres_primary_dual": "postgres->mongo"}


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
    """``store`` while it is unreachable: every call fails. The methods keep
    their write markers, since the routing layer reads them off the Mongo side."""

    def __init__(self, store):
        self._store = store

    async def replay_write(self, documents):
        raise ConnectionError("store unreachable")

    def __getattr__(self, name):
        @functools.wraps(getattr(self._store, name))
        async def fail(*args, **kwargs):
            raise ConnectionError("store unreachable")

        return fail


def routed(group, mode, mongo, postgres, *, mirror_down=False):
    flags = load_flags({"DB_WRITE_MODE": mode})
    if mirror_down:
        if flags.mirror_store(group) is ReadSource.POSTGRES:
            postgres = Down(postgres)
        else:
            mongo = Down(mongo)
    return RoutingRepository(
        group=group,
        flags=flags,
        mongo=mongo,
        postgres=postgres,
        on_mirror_failure=container.outbox_recorder(),
    )


def forms_repo(mode, **kw):
    sessions = container.pg_sessionmaker()
    return routed(
        "forms",
        mode,
        FormRepository(),
        PostgresFormRepository(
            sessions,
            container.responder_groups_repository(),
            container.form_response_repo(),
        ),
        **kw,
    )


async def verify(target, *collections):
    async with Runner(target) as runner:
        reports = await runner.verify(list(collections))
    return {r.collection: r.as_dict() for r in reports if not r.clean}


@pytest.mark.parametrize("mode", MODES)
async def test_a_replayed_insert_verifies_clean(target, mode):
    repo = routed(
        "refdata",
        mode,
        AllowedOriginsRepository(),
        PostgresAllowedOriginsRepository(container.pg_sessionmaker()),
    )
    await repo.add("https://a.example")
    await repo.add("https://b.example")
    assert await verify(target, "allowed_origins") == {}


@pytest.mark.parametrize("mode", MODES)
async def test_form_writes_that_move_updated_at_verify_clean(target, mode):
    repo = forms_repo(mode)
    created = await repo.create_form(
        StandardForm(
            form_id=str(PydanticObjectId()), title="Draft", builder_version="v2"
        )
    )
    assert await verify(target, "forms") == {}

    # re-executed on the mirror: each store's save stamps updated_at
    document = await repo.get_form_document_by_id(created.form_id)
    document.title = "Renamed"
    await repo.save_form(document)
    assert await verify(target, "forms") == {}

    # replayed: the conditional save moves updated_at past the stored value
    stored = await repo.get_form_document_by_id(created.form_id)
    updated = await repo.update_form_if_unchanged(
        PydanticObjectId(created.form_id),
        StandardForm(form_id=created.form_id, title="Again", builder_version="v2"),
        stored.updated_at,
    )
    assert updated.updated_at > stored.updated_at
    assert await verify(target, "forms") == {}


@pytest.mark.parametrize("mode", MODES)
async def test_a_save_of_a_document_each_store_loads_itself_verifies_clean(
    target, mode
):
    """Each store loads the template and saves it; ``MongoDocument.save``
    moves updated_at, and the Postgres twin now does the same."""
    routed_templates = container.form_template_repo()
    repo = routed(
        "forms",
        mode,
        routed_templates.store(ReadSource.MONGO),
        routed_templates.store(ReadSource.POSTGRES),
    )
    template = await repo.create_new_template(
        PydanticObjectId(), StandardFormTemplate(title="T"), testUser
    )
    assert await verify(target, "form_templates") == {}
    updated = await repo.update_template(
        template.id, StandardFormTemplate(title="T2", description="d")
    )
    assert updated.updated_at > template.updated_at
    assert await verify(target, "form_templates") == {}


@pytest.mark.parametrize("mode", MODES)
async def test_a_counter_created_and_bumped_on_both_stores_verifies_clean(target, mode):
    repo = routed(
        "ai",
        mode,
        RateLimitRepository(),
        PostgresRateLimitRepository(container.pg_sessionmaker()),
    )
    counter_id = str(PydanticObjectId())
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
    assert await repo.hit(counter_id, expires) == 1
    assert await verify(target, "rate_limit_counters") == {}
    assert await repo.hit(counter_id, expires) == 2
    assert await verify(target, "rate_limit_counters") == {}


@pytest.mark.parametrize("mode", MODES)
async def test_documents_built_on_both_stores_verify_clean(target, mode):
    repo = routed(
        "responses",
        mode,
        ResponderGroupsRepository(),
        PostgresResponderGroupsRepository(container.pg_sessionmaker()),
    )
    group = await repo.create_group(PydanticObjectId(), "Group")
    await repo.add_emails_to_group(group.id, ["a@example.com", "b@example.com"])
    await repo.add_group_to_form(str(PydanticObjectId()), group.id)
    assert (
        await verify(
            target,
            "responder_group",
            "responder_group_member",
            "responder_group_form",
        )
        == {}
    )


@pytest.mark.parametrize("mode", MODES)
async def test_a_failed_mirror_write_is_repaired_by_reconcile(target, mode):
    healthy = forms_repo(mode)
    created = await healthy.create_form(
        StandardForm(
            form_id=str(PydanticObjectId()), title="Draft", builder_version="v2"
        )
    )
    document = await healthy.get_form_document_by_id(created.form_id)

    down = forms_repo(mode, mirror_down=True)
    document.title = "Changed while the mirror was down"
    await down.save_form(document)
    await down.create_form(
        StandardForm(form_id=str(PydanticObjectId()), title="New", builder_version="v2")
    )
    assert down.metrics.mirror_failures[("forms", "save_form")] == 1
    assert down.metrics.mirror_failures[("forms", "create_form")] == 1

    differs = await verify(target, "forms")
    assert differs["forms"]["mismatched"] == 1
    assert (
        differs["forms"][
            "missing_in_postgres" if mode == "dual" else "missing_in_mongo"
        ]
        == 1
    )

    async with Runner(target) as runner:
        assert (await runner.status())["outbox"][
            "mongo" if mode == "dual" else "postgres"
        ] == 2
        await runner.reconcile(["forms"], direction=DIRECTION[mode])
        assert (await runner.status())["outbox"] == {"mongo": 0, "postgres": 0}
    assert await verify(target, "forms") == {}

    # and the stores stay in line for the next write
    document = await healthy.get_form_document_by_id(created.form_id)
    document.title = "After the repair"
    await healthy.save_form(document)
    assert await verify(target, "forms") == {}


async def test_a_replayed_document_is_stored_exactly_on_mongo(clean_postgres):
    """The reverse mirror replaces the Mongo copy with the primary's document:
    updated_at is not re-stamped and keys the primary dropped do not linger."""
    repo = forms_repo("postgres_primary_dual")
    created = await repo.create_form(
        StandardForm(
            form_id=str(PydanticObjectId()), title="Draft", builder_version="v2"
        )
    )
    collection = FormDocument.get_pymongo_collection()
    await collection.update_one({"_id": created.id}, {"$set": {"stale_key": 1}})
    stored = await repo.get_form_document_by_id(created.form_id)
    await repo.update_form_if_unchanged(
        PydanticObjectId(created.form_id),
        StandardForm(form_id=created.form_id, title="Again", builder_version="v2"),
        stored.updated_at,
    )
    raw = await collection.find_one({"_id": created.id})
    row = await PostgresFormRepository(
        container.pg_sessionmaker(), None, None
    ).get_form_document_by_id(created.form_id)
    assert "stale_key" not in raw
    assert raw["title"] == "Again"
    assert FormDocument.model_validate(raw).updated_at == row.updated_at
