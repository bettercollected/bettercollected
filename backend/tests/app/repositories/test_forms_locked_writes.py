"""The write methods of the forms' Postgres twins apply their change to the
stored copy under its row lock: ``set_form_logo`` sets the logo alone, like
Mongo's ``$set`` of ``logo``; the whole-form save, an action's secret, a
workspace link's settings and a template's content are applied to the stored
copy, not to one the caller read earlier. The twins are the primary from
``postgres_primary_dual`` on: a whole-document save from a copy read before
a concurrent write would undo that write (a removed action's encrypted
credentials back on the form, an autosave rolled back, a deleted draft,
link or template stored again). Skipped unless DATABASE_URL points at a
*_test database."""

import asyncio

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select, text

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.models.template import StandardFormTemplate
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.db.models import FormRow, FormTemplateRow, WorkspaceFormRow
from common.db import from_row_doc
from common.models.standard_form import StandardForm

ACTION = str(PydanticObjectId())
KEPT = str(PydanticObjectId())


@pytest.fixture
def repo(clean_postgres):
    return PostgresFormRepository(container.pg_sessionmaker(), None, None)


def draft(**extra) -> FormDocument:
    return FormDocument(
        id=PydanticObjectId(),
        form_id=str(PydanticObjectId()),
        title="Draft",
        builder_version="v2",
        actions={
            "on_submit": [{"id": ACTION, "enabled": True}, {"id": KEPT}],
        },
        parameters={
            ACTION: [{"name": "sheet", "value": "s-1"}],
            KEPT: [{"name": "to", "value": "x"}],
        },
        secrets={
            ACTION: [{"name": "Credentials", "value": "encrypted-1"}],
            KEPT: [{"name": "Credentials", "value": "encrypted-2"}],
        },
        **extra,
    )


async def stored(form_id):
    async with container.pg_sessionmaker()() as session:
        doc = (
            await session.execute(select(FormRow.doc).where(FormRow.form_id == form_id))
        ).scalar_one_or_none()
    return None if doc is None else from_row_doc(FormDocument, doc)


async def waiting_for_locks(count: int) -> None:
    """Until ``count`` sessions of this database wait for a lock."""
    for _ in range(200):
        async with container.pg_sessionmaker()() as session:
            waiting = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND wait_event_type = 'Lock'"
                    )
                )
            ).scalar_one()
        if waiting >= count:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"expected {count} sessions waiting for a lock")


async def interleaved(locked, first_write, second_write):
    """Hold the row lock ``locked`` (a SELECT) takes while ``first_write``
    starts and waits for it, then while ``second_write`` starts; release
    it. ``first_write`` then runs first; a ``second_write`` that doesn't
    lock has read the row before it."""
    async with container.pg_sessionmaker()() as holder, holder.begin():
        await holder.execute(locked.with_for_update())
        first = asyncio.create_task(first_write())
        await waiting_for_locks(1)
        second = asyncio.create_task(second_write())
        await waiting_for_locks(2)
    await asyncio.wait_for(first, 10)
    return await asyncio.wait_for(second, 10)


def draft_row(form_id):
    return select(FormRow.id).where(FormRow.form_id == form_id)


async def logo_after(repo, form_id, first_write, logo="https://logo/new.png"):
    return await interleaved(
        draft_row(form_id), first_write, lambda: repo.set_form_logo(form_id, logo)
    )


async def test_sets_only_the_logo_and_keeps_updated_at(repo):
    form = draft(logo="https://logo/old.png")
    await repo.save_form(form)
    before = await stored(form.form_id)

    returned = await repo.set_form_logo(form.form_id, "https://logo/new.png")

    after = await stored(form.form_id)
    assert after.logo == "https://logo/new.png"
    assert returned.logo == "https://logo/new.png"
    assert after.updated_at == before.updated_at
    assert after.title == "Draft" and set(after.secrets) == {ACTION, KEPT}

    await repo.set_form_logo(form.form_id, None)
    assert (await stored(form.form_id)).logo is None


async def test_a_removed_action_stays_removed(repo):
    form = draft()
    await repo.save_form(form)

    await logo_after(
        repo, form.form_id, lambda: repo.remove_action_from_all_forms(ACTION)
    )

    after = await stored(form.form_id)
    assert after.logo == "https://logo/new.png"
    assert ACTION not in after.secrets and ACTION not in after.parameters
    assert [str(s.id) for s in after.actions["on_submit"]] == [KEPT]
    assert after.secrets[KEPT][0].value == "encrypted-2"


async def test_an_autosave_is_not_rolled_back(repo):
    form = draft()
    await repo.save_form(form)
    before = await stored(form.form_id)
    saved = StandardForm(form_id=form.form_id, title="Autosaved")

    await logo_after(
        repo,
        form.form_id,
        lambda: repo.update_form_if_unchanged(form.form_id, saved, before.updated_at),
    )

    after = await stored(form.form_id)
    assert after.title == "Autosaved"
    assert after.logo == "https://logo/new.png"
    # the autosave's updated_at, kept by the logo write
    assert after.updated_at > before.updated_at


async def test_a_deleted_draft_is_not_stored_again(repo):
    form = draft()
    await repo.save_form(form)

    returned = await logo_after(
        repo, form.form_id, lambda: repo.delete_form(form.form_id)
    )

    assert returned is None
    assert await stored(form.form_id) is None


async def test_a_draft_not_stored_stays_so(repo):
    assert await repo.set_form_logo(str(PydanticObjectId()), "https://l") is None
    async with container.pg_sessionmaker()() as session:
        any_row = (
            await session.execute(select(FormRow.id).limit(1))
        ).scalar_one_or_none()
    assert any_row is None


async def test_a_whole_form_save_keeps_a_removed_action_removed(repo):
    form = draft()
    await repo.save_form(form)
    saved = StandardForm(form_id=form.form_id, title="Saved")

    await interleaved(
        draft_row(form.form_id),
        lambda: repo.remove_action_from_all_forms(ACTION),
        lambda: repo.update_form(form.form_id, saved),
    )

    after = await stored(form.form_id)
    assert after.title == "Saved"
    assert ACTION not in after.secrets and ACTION not in after.parameters
    assert [str(s.id) for s in after.actions["on_submit"]] == [KEPT]


async def test_a_whole_form_save_does_not_store_a_deleted_draft_again(repo):
    form = draft()
    await repo.save_form(form)

    returned = await interleaved(
        draft_row(form.form_id),
        lambda: repo.delete_form(form.form_id),
        lambda: repo.update_form(
            form.form_id, StandardForm(form_id=form.form_id, title="Saved")
        ),
    )

    assert returned is None
    assert await stored(form.form_id) is None


async def test_an_actions_secret_is_set_on_the_stored_draft(repo):
    form = draft()
    await repo.save_form(form)
    read_before = await stored(form.form_id)  # still holds KEPT
    payload = FormActionsDto(name="Credentials", value="encrypted-3", type="secrets")

    returned = await interleaved(
        draft_row(form.form_id),
        lambda: repo.remove_action_from_all_forms(KEPT),
        lambda: repo.update_form_actions(form.form_id, ACTION, read_before, payload),
    )

    after = await stored(form.form_id)
    assert after.secrets[ACTION][0].value == "encrypted-3"
    assert KEPT not in after.secrets and KEPT not in after.parameters
    assert [str(s.id) for s in after.actions["on_submit"]] == [ACTION]
    assert returned.secrets[ACTION][0].value == "encrypted-3"
    assert after.updated_at > read_before.updated_at


@pytest.fixture
def links(clean_postgres):
    return PostgresWorkspaceFormRepository(container.pg_sessionmaker(), None)


def link_row(link_id):
    return select(WorkspaceFormRow.id).where(WorkspaceFormRow.id == str(link_id))


async def test_a_links_settings_update_does_not_store_a_deleted_link_again(links):
    link = WorkspaceFormDocument(
        workspace_id=PydanticObjectId(),
        form_id="f-1",
        user_id="u-1",
        settings=WorkspaceFormSettings(),
    )
    await links.save(link)
    stale = await links.find_workspace_form(link.workspace_id, "f-1")
    stale.settings.pinned = True

    updating = interleaved(
        link_row(link.id),
        lambda: links.delete_form_in_workspace(link.workspace_id, "f-1"),
        lambda: links.update(str(link.id), stale),
    )

    with pytest.raises(HTTPException) as refused:
        await updating
    assert refused.value.status_code == 404
    assert await links.find_workspace_form(link.workspace_id, "f-1") is None


async def test_a_links_settings_are_stored_on_the_stored_link(links):
    link = WorkspaceFormDocument(
        workspace_id=PydanticObjectId(),
        form_id="f-2",
        user_id="u-1",
        settings=WorkspaceFormSettings(),
    )
    await links.save(link)
    stale = await links.find_workspace_form(link.workspace_id, "f-2")
    stale.settings.pinned = True
    stale.user_id = "someone-else"  # not a field the callers change

    await links.update(str(link.id), stale)
    again = await links.save_workspace_form(
        link.workspace_id, "f-2", "u-1", WorkspaceFormSettings(hidden=True)
    )

    after = await links.find_workspace_form(link.workspace_id, "f-2")
    assert after.user_id == "u-1" and after.id == link.id == again.id
    assert after.settings.hidden is True


@pytest.fixture
def templates(clean_postgres):
    return PostgresFormTemplateRepository(container.pg_sessionmaker(), None)


async def test_a_template_update_does_not_store_a_deleted_template_again(templates):
    template = await templates.save(
        FormTemplateDocument(title="T", workspace_id=PydanticObjectId())
    )

    returned = await interleaved(
        select(FormTemplateRow.id).where(FormTemplateRow.id == str(template.id)),
        lambda: templates.delete_template(template.id),
        lambda: templates.update_template(
            template.id, StandardFormTemplate(title="Changed")
        ),
    )

    assert returned is None
    assert await templates.get_template_by_id(template.id) is None
