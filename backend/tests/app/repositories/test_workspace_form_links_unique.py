"""A form is linked to a workspace once: unique (workspace_id, form_id) in both stores.

Mongo: the ``uq_workspace_forms_workspace_form`` IndexModel (built at startup);
Postgres: app revision 0019. Re-saving a link that exists is a no-op that
returns the existing link, in every storage mode.
"""

import pytest
from beanie import PydanticObjectId
from beanie.odm.fields import IndexModelField
from pymongo.errors import DuplicateKeyError, OperationFailure
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
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


async def test_mongo_refuses_a_second_link_of_the_same_form():
    ws, other = PydanticObjectId(), PydanticObjectId()
    await link(ws, "f1", "u1").insert()
    await link(other, "f1", "u1").insert()  # another workspace: fine
    await link(ws, "f2", "u1").insert()  # another form: fine
    with pytest.raises(DuplicateKeyError, match=INDEX):
        await link(ws, "f1", "u2").insert()
    assert await WorkspaceFormDocument.find({"workspace_id": ws}).count() == 2


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


async def test_postgres_refuses_a_second_link_of_the_same_form(postgres_repo):
    ws, other = PydanticObjectId(), PydanticObjectId()
    await postgres_repo.save(link(ws, "f1", "u1"))
    await postgres_repo.save(link(other, "f1", "u1"))
    await postgres_repo.save(link(ws, "f2", "u1"))
    with pytest.raises(IntegrityError, match=INDEX):
        await postgres_repo.save(link(ws, "f1", "u2"))
    assert len(await postgres_repo.list_in_workspace(ws)) == 2


@pytest.mark.parametrize("store", ["mongo", "postgres"])
async def test_save_workspace_form_returns_the_existing_link(store, postgres_repo):
    repo = WorkspaceFormRepository() if store == "mongo" else postgres_repo
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
    flags = container.flags()
    if flags.requires_postgres():
        postgres = PostgresWorkspaceFormRepository(
            container.pg_sessionmaker(), ResponderGroupsRepository()
        )
        rows = await postgres.list_in_workspace(ws)
        assert [(str(r.id), r.user_id) for r in rows] == [(str(first.id), "u1")]


async def test_mongo_startup_index_refuses_duplicates_by_name():
    """The application database got the unique index at startup; a database
    still holding duplicate links can't get it, and the error names it."""
    client = container.database_client()
    app_db = settings.mongo_settings.DB
    info = await client[app_db]["workspace_forms"].index_information()
    assert info[INDEX]["unique"] is True
    assert info[INDEX]["key"] == [("workspace_id", 1), ("form_id", 1)]

    db = client[app_db + "_wfdups"]
    try:
        ws = PydanticObjectId()
        await db["workspace_forms"].insert_many(
            [
                {"workspace_id": ws, "form_id": "f1", "user_id": "u1"},
                {"workspace_id": ws, "form_id": "f1", "user_id": "u2"},
            ]
        )
        # what Beanie runs at startup for this document's declared indexes
        declared = IndexModelField.list_to_index_model(
            WorkspaceFormDocument.get_settings().indexes
        )
        with pytest.raises(OperationFailure, match=INDEX):
            await db["workspace_forms"].create_indexes(declared)
        await db["workspace_forms"].delete_many({"user_id": "u2"})
        assert await db["workspace_forms"].create_indexes(declared) == [INDEX]
    finally:
        await client.drop_database(app_db + "_wfdups")
