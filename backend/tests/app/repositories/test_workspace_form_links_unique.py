"""A form is linked to a workspace once: unique (workspace_id, form_id), app
revision 0019. Re-saving a link that exists is a no-op that returns the
existing link.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.records import RecordId

INDEX = "uq_workspace_forms_workspace_form"


def link(workspace_id, form_id, user_id, **settings_):
    return WorkspaceFormDocument(
        id=RecordId(),
        workspace_id=workspace_id,
        form_id=form_id,
        user_id=user_id,
        settings=WorkspaceFormSettings(**settings_),
    )


@pytest.fixture
def postgres_repo(clean_postgres):
    return PostgresWorkspaceFormRepository(
        container.pg_sessionmaker(), container.responder_groups_repository()
    )


async def _save_workspace_form_returns_the_existing_link(repo):
    ws = RecordId()
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


async def test_postgres_refuses_a_second_link_of_the_same_form(postgres_repo):
    ws, other = RecordId(), RecordId()
    await postgres_repo.save(link(ws, "f1", "u1"))
    await postgres_repo.save(link(other, "f1", "u1"))
    await postgres_repo.save(link(ws, "f2", "u1"))
    with pytest.raises(IntegrityError, match=INDEX):
        await postgres_repo.save(link(ws, "f1", "u2"))
    assert len(await postgres_repo.list_in_workspace(ws)) == 2


async def test_postgres_links_without_a_workspace_are_distinct(postgres_repo):
    """NULLs are distinct in the index: links without a workspace never
    collide (as 4.0's partial Mongo index left them out)."""

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


async def test_the_containers_save_workspace_form_keeps_one_link():
    """A second importer's save is a no-op."""
    repo = container.workspace_form_repo()
    ws = RecordId()
    first = await repo.save_workspace_form(
        ws, "f1", "u1", WorkspaceFormSettings(custom_url="first")
    )
    second = await repo.save_workspace_form(
        ws, "f1", "u2", WorkspaceFormSettings(custom_url="second")
    )
    assert str(second.id) == str(first.id)
    rows = await repo.list_in_workspace(ws)
    assert [(str(r.id), r.user_id) for r in rows] == [(str(first.id), "u1")]


async def test_a_workspaces_links_keep_their_insertion_order(postgres_repo):
    ws = RecordId()
    for form_id in ("pub", "closed", "open"):
        await postgres_repo.save(link(ws, form_id, "u1"))
    assert [wf.form_id for wf in await postgres_repo.list_in_workspace(ws)] == [
        "pub",
        "closed",
        "open",
    ]
    assert await postgres_repo.get_form_ids_imported_by_user(ws, "u1") == [
        "pub",
        "closed",
        "open",
    ]
