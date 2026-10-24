"""A form is linked to a workspace once: unique (workspace_id, form_id) in both stores.

Postgres: app revision 0019. Mongo: ``uq_workspace_forms_workspace_form``,
built at startup after Beanie; a Mongo database still holding duplicate links
starts anyway and logs an error with their count. Re-saving a link that exists
is a no-op that returns the existing link, in every storage mode.
"""

import pytest
from beanie import PydanticObjectId
from loguru import logger
from pymongo.errors import DuplicateKeyError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.handlers.database import ensure_workspace_form_unique_index, init_db
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.config import settings

INDEX = "uq_workspace_forms_workspace_form"


def link(workspace_id, form_id, user_id, **settings_):
    return WorkspaceFormDocument(
        id=PydanticObjectId(),
        workspace_id=workspace_id,
        form_id=form_id,
        user_id=user_id,
        settings=WorkspaceFormSettings(**settings_),
    )


@pytest.fixture
def postgres_repo(clean_postgres):
    return PostgresWorkspaceFormRepository(
        container.pg_sessionmaker(), ResponderGroupsRepository()
    )


async def _save_workspace_form_returns_the_existing_link(repo):
    ws = PydanticObjectId()
    first = await repo.save_workspace_form(
        ws, "f1", "u1", WorkspaceFormSettings(custom_url="first")
    )
    # the same user re-saving updates the link's settings, as before
    again = await repo.save_workspace_form(
        ws, "f1", "u1", WorkspaceFormSettings(custom_url="again")
    )
    assert str(again.id) == str(first.id)
    assert again.settings.custom_url == "again"
    # another user (another importer, a racing import): the existing link, unchanged
    other = await repo.save_workspace_form(
        ws, "f1", "u2", WorkspaceFormSettings(custom_url="other")
    )
    assert str(other.id) == str(first.id)
    assert other.user_id == "u1" and other.settings.custom_url == "again"
    links = await repo.list_in_workspace(ws)
    assert [(str(wf.id), wf.settings.custom_url) for wf in links] == [
        (str(first.id), "again")
    ]


# -- Postgres ----------------------------------------------------------------------
async def test_postgres_refuses_a_second_link_of_the_same_form(postgres_repo):
    ws, other = PydanticObjectId(), PydanticObjectId()
    await postgres_repo.save(link(ws, "f1", "u1"))
    await postgres_repo.save(link(other, "f1", "u1"))
    await postgres_repo.save(link(ws, "f2", "u1"))
    with pytest.raises(IntegrityError, match=INDEX):
        await postgres_repo.save(link(ws, "f1", "u2"))
    assert len(await postgres_repo.list_in_workspace(ws)) == 2


async def test_postgres_links_without_a_workspace_are_distinct(postgres_repo):
    """NULLs are distinct in the Postgres index: links without a workspace
    never collide (Mongo's partial index leaves them out alike)."""

    def insert(oid):
        return text(
            "INSERT INTO app.workspace_forms (id, doc, _bc_checksum) VALUES "
            f"('{oid}', jsonb_build_object('_id', jsonb_build_object('$oid', "
            f"'{oid}'), 'form_id', 'f1', 'user_id', 'u1'), 'x')"
        )

    async with container.pg_engine().begin() as conn:
        await conn.execute(insert("a" * 24))
        await conn.execute(insert("b" * 24))


async def test_postgres_save_workspace_form_returns_the_existing_link(postgres_repo):
    await _save_workspace_form_returns_the_existing_link(postgres_repo)


async def test_routed_save_workspace_form_keeps_one_link_in_every_mode():
    """Whatever the storage mode, a second importer's save is a no-op in the
    primary store and in its mirror."""
    repo = container.workspace_form_repo()
    ws = PydanticObjectId()
    first = await repo.save_workspace_form(
        ws, "f1", "u1", WorkspaceFormSettings(custom_url="first")
    )
    second = await repo.save_workspace_form(
        ws, "f1", "u2", WorkspaceFormSettings(custom_url="second")
    )
    assert str(second.id) == str(first.id)
    assert [str(wf.id) for wf in await repo.list_in_workspace(ws)] == [str(first.id)]
    if container.flags().writes_postgres("forms"):
        postgres = PostgresWorkspaceFormRepository(
            container.pg_sessionmaker(), ResponderGroupsRepository()
        )
        rows = await postgres.list_in_workspace(ws)
        assert [(str(r.id), r.user_id) for r in rows] == [(str(first.id), "u1")]


# -- Mongo (marked ``mongo`` in tests/conftest.py) ----------------------------------
async def test_mongo_refuses_a_second_link_of_the_same_form():
    ws, other = PydanticObjectId(), PydanticObjectId()
    await link(ws, "f1", "u1").insert()
    await link(other, "f1", "u1").insert()  # another workspace: fine
    await link(ws, "f2", "u1").insert()  # another form: fine
    with pytest.raises(DuplicateKeyError, match=INDEX):
        await link(ws, "f1", "u2").insert()
    assert await WorkspaceFormDocument.find({"workspace_id": ws}).count() == 2


async def test_mongo_links_without_a_workspace_are_not_indexed():
    """As Postgres treats NULLs as distinct: links whose workspace_id is null
    or missing never collide; a string workspace id is indexed like Postgres's
    text column."""
    collection = WorkspaceFormDocument.get_pymongo_collection()
    await collection.insert_many(
        [
            {"workspace_id": None, "form_id": "f1", "user_id": "u1"},
            {"workspace_id": None, "form_id": "f1", "user_id": "u2"},
            {"form_id": "f1", "user_id": "u1"},
            {"form_id": "f1", "user_id": "u2"},
            {"workspace_id": "ws-as-text", "form_id": "f1", "user_id": "u1"},
        ]
    )
    with pytest.raises(DuplicateKeyError, match=INDEX):
        await collection.insert_one(
            {"workspace_id": "ws-as-text", "form_id": "f1", "user_id": "u2"}
        )


async def test_mongo_save_workspace_form_returns_the_existing_link():
    await _save_workspace_form_returns_the_existing_link(WorkspaceFormRepository())


async def test_a_workspaces_links_keep_their_order_in_both_stores(postgres_repo):
    """The index must not reorder unsorted reads: a workspace's links come
    back in insertion order from Mongo, as Postgres orders them."""
    mongo, ws = WorkspaceFormRepository(), PydanticObjectId()
    for form_id in ("pub", "closed", "open"):
        document = link(ws, form_id, "u1")
        await mongo.save(document)
        await postgres_repo.save(document)
    for repo in (mongo, postgres_repo):
        assert [wf.form_id for wf in await repo.list_in_workspace(ws)] == [
            "pub",
            "closed",
            "open",
        ]
        assert await repo.get_form_ids_imported_by_user(ws, "u1") == [
            "pub",
            "closed",
            "open",
        ]


async def test_the_index_is_built_after_beanie_and_skipped_on_duplicates():
    """The application database got the index at startup. On a database still
    holding duplicate links it is not built: an error with their count, no
    crash; once resolved, it is."""
    client = container.database_client()
    app_db = settings.mongo_settings.DB
    info = await client[app_db]["workspace_forms"].index_information()
    assert info[INDEX]["unique"] is True
    assert info[INDEX]["key"] == [("workspace_id", 1), ("form_id", 1)]
    assert not WorkspaceFormDocument.get_settings().indexes  # not Beanie's

    name = app_db + "_wfdups"
    db = client[name]
    logged = []
    sink = logger.add(lambda m: logged.append(str(m)), level="ERROR")
    try:
        ws = PydanticObjectId()
        await db["workspace_forms"].insert_many(
            [
                {"workspace_id": ws, "form_id": "f1", "user_id": "u1"},
                {"workspace_id": ws, "form_id": "f1", "user_id": "u2"},
                {"workspace_id": ws, "form_id": "f2", "user_id": "u1"},
            ]
        )
        assert await ensure_workspace_form_unique_index(db) is False
        assert INDEX not in await db["workspace_forms"].index_information()
        (message,) = [m for m in logged if INDEX in m]
        assert "linked more than once: 1." in message
        assert str(ws) not in message  # counts only

        await db["workspace_forms"].delete_many({"user_id": "u2"})
        assert await ensure_workspace_form_unique_index(db) is True
        assert INDEX in await db["workspace_forms"].index_information()
    finally:
        logger.remove(sink)
        await client.drop_database(name)


async def test_a_mongo_holding_duplicate_links_still_starts():
    """The startup Mongo set-up (Beanie and the indexes after it) runs to the
    end on a database holding duplicate links."""
    client = container.database_client()
    app_db = settings.mongo_settings.DB
    name = app_db + "_wfstart"
    ws = PydanticObjectId()
    await client[name]["workspace_forms"].insert_many(
        [
            {"workspace_id": ws, "form_id": "f1", "user_id": "u1"},
            {"workspace_id": ws, "form_id": "f1", "user_id": "u2"},
        ]
    )
    logged = []
    sink = logger.add(lambda m: logged.append(str(m)), level="INFO")
    try:
        await init_db(name, client, required=True)
        assert any("Database connected successfully" in m for m in logged)
        assert any(INDEX in m and "linked more than once: 1." in m for m in logged)
    finally:
        logger.remove(sink)
        # Beanie back on the test database
        await init_db(app_db, client, required=True)
        await client.drop_database(name)
    assert await WorkspaceFormDocument.find({"workspace_id": ws}).count() == 0
