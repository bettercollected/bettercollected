"""The access mode of a form survives what races with it.

* A save of a link read earlier (the AI chat's settings ops, the insights
  switch, the builder's settings, a duplicate's bookkeeping) never writes a
  stale mode back: a restriction set between the read and the save stays.
* A copy of a restricted form is stored with its mode in one write: it never
  exists open, and when the write fails nothing is left.
"""

import pytest

from backend.app.container import container
from backend.app.services.form_access.model import MODE_RESTRICTED
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import create_form, restrict
from tests.app.form_access.test_switch_and_memo import statements


async def _link(workspace, form_id):
    return await container.workspace_form_repo().find_workspace_form(
        workspace.id, str(form_id)
    )


async def test_a_restriction_set_between_the_read_and_the_save_survives(
    workspace, switch_on
):
    form = await create_form(workspace, testUser)
    repo = container.workspace_form_repo()
    stale = await _link(workspace, form.form_id)  # read: no mode yet
    assert stale.settings.access_mode is None
    await restrict(workspace, form.form_id)  # a restriction lands meanwhile
    stale.settings.pinned = True  # the caller's own change
    await repo.save(stale)
    stored = await _link(workspace, form.form_id)
    assert stored.settings.access_mode == MODE_RESTRICTED
    assert stored.settings.pinned is True


async def test_a_stale_save_cannot_lift_a_restriction_either_way(workspace, switch_on):
    """The caller read a restricted link; an Admin opened the form meanwhile:
    the save keeps what is stored now, not what it read."""
    form = await create_form(workspace, testUser)
    repo = container.workspace_form_repo()
    await restrict(workspace, form.form_id)
    stale = await _link(workspace, form.form_id)
    await repo.set_access_mode(workspace.id, str(form.form_id), "workspace")
    stale.settings.pinned = True
    await repo.save(stale)
    assert (await _link(workspace, form.form_id)).settings.access_mode == "workspace"


async def test_a_caller_cannot_set_the_mode_through_a_save(workspace, switch_on):
    form = await create_form(workspace, testUser)
    link = await _link(workspace, form.form_id)
    link.settings.access_mode = MODE_RESTRICTED
    await container.workspace_form_repo().save(link)
    assert (await _link(workspace, form.form_id)).settings.access_mode is None


async def test_off_a_save_is_one_statement_as_before_and_on_it_takes_the_lock(
    workspace, monkeypatch
):
    from backend.config import settings

    form = await create_form(workspace, testUser)
    repo = container.workspace_form_repo()
    link = await _link(workspace, form.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    with statements() as off:
        await repo.save(link)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    with statements() as on:
        await repo.save(link)
    writes = [s for s in off if "INSERT INTO" in s]
    assert len(off) == 1 and len(writes) == 1
    assert len(on) == 2 and any("FOR UPDATE" in s for s in on)


async def test_a_copy_of_a_restricted_form_is_stored_with_its_mode_in_one_write(
    workspace, switch_on
):
    source = await create_form(workspace, testUser)
    await restrict(workspace, source.form_id)
    with statements() as seen:
        copy = await container.workspace_form_service().duplicate_form(
            workspace.id, source.form_id, testUser
        )
    link_writes = [
        s for s in seen if "INSERT INTO app.workspace_forms" in s
    ]
    assert len(link_writes) == 1
    assert (await _link(workspace, copy.form_id)).settings.access_mode == MODE_RESTRICTED


async def test_when_storing_the_copy_fails_no_open_copy_remains(
    workspace, switch_on, monkeypatch
):
    source = await create_form(workspace, testUser)
    await restrict(workspace, source.form_id)
    repo = container.workspace_form_repo()
    before = {str(link.form_id) for link in await repo.list_in_workspace(workspace.id)}

    async def refuse(*_args, **_kwargs):
        raise RuntimeError("the write failed")

    monkeypatch.setattr(repo, "save_document", refuse)
    with pytest.raises(RuntimeError):
        await container.workspace_form_service().duplicate_form(
            workspace.id, source.form_id, testUser
        )
    monkeypatch.undo()
    after = {str(link.form_id) for link in await repo.list_in_workspace(workspace.id)}
    # no link of the copy exists, open or otherwise
    assert after == before
