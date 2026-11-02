"""Saving a restricted form as a workspace template.

A template has no access mode: every member of the workspace sees it, so the
structure of a restricted form would reach people the form is closed to. While
``FORM_ACCESS_ENABLED`` is on only an Owner, an Admin or the form's creator may
do it (403 ``template_from_restricted_form``); a member the form is closed to
still gets the 404 of an unknown form. Open forms and the switch-off behaviour
are as before. The check runs before anything is copied.
"""

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.form_access_grant import ROLE_EDITOR
from backend.app.services.form_access.mode import (
    TEMPLATE_FROM_RESTRICTED_CODE,
    TEMPLATE_FROM_RESTRICTED_MESSAGE,
)
from backend.app.services.form_access.model import MODE_WORKSPACE
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    cookies,
    create_form,
    grant,
    restrict,
    set_mode,
)


async def _templates(workspace):
    return await container.form_template_repo().get_templates_with_creator(
        workspace_id=workspace.id
    )


async def _save_as_template(workspace, form, user):
    return await container.workspace_form_service().duplicate_form(
        workspace.id, form.form_id, user, is_template=True
    )


async def _refused(workspace, form, user, status, code=None):
    before = len(await _templates(workspace))
    with pytest.raises(HTTPException) as refusal:
        await _save_as_template(workspace, form, user)
    assert refusal.value.status_code == status
    if code is not None:
        assert refusal.value.content == {
            "code": code,
            "message": TEMPLATE_FROM_RESTRICTED_MESSAGE,
        }
    # nothing was copied
    assert len(await _templates(workspace)) == before


@pytest.fixture()
async def restricted(workspace, monkeypatch):
    """A restricted form made by a workspace Editor (the creator), with a
    Viewer holding an Editor grant, an Editor holding an Editor grant, an
    Editor with no way in and an Admin; the switch is on."""
    creator = await add_member(workspace, "EDITOR")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)
    grantee = await add_member(workspace, "VIEWER")
    await grant(workspace, form.form_id, grantee.id, ROLE_EDITOR)
    editor_grantee = await add_member(workspace, "EDITOR")
    await grant(workspace, form.form_id, editor_grantee.id, ROLE_EDITOR)
    outsider = await add_member(workspace, "EDITOR")
    admin = await add_member(workspace, "ADMIN")
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    return dict(
        workspace=workspace,
        form=form,
        creator=creator,
        grantee=grantee,
        editor_grantee=editor_grantee,
        outsider=outsider,
        admin=admin,
    )


async def test_the_owner_an_admin_and_the_creator_may_save_it(restricted):
    workspace, form = restricted["workspace"], restricted["form"]
    for who in (testUser, restricted["admin"], restricted["creator"]):
        template = await _save_as_template(workspace, form, who)
        assert str(template.workspace_id) == str(workspace.id)
    assert len(await _templates(workspace)) == 3


async def test_a_grantee_editor_is_refused_with_a_code(restricted):
    await _refused(
        restricted["workspace"],
        restricted["form"],
        restricted["editor_grantee"],
        403,
        TEMPLATE_FROM_RESTRICTED_CODE,
    )
    # a Viewer holding an Editor grant lacks form.create by role: refused
    # earlier, as before, with the plain 403
    await _refused(restricted["workspace"], restricted["form"], restricted["grantee"], 403)


async def test_an_editor_who_is_closed_out_of_the_form_still_gets_the_404(restricted):
    await _refused(restricted["workspace"], restricted["form"], restricted["outsider"], 404)


async def test_the_same_editors_may_save_an_open_form(restricted):
    workspace, form = restricted["workspace"], restricted["form"]
    await set_mode(workspace, form.form_id, MODE_WORKSPACE)
    for who in (restricted["editor_grantee"], restricted["outsider"]):
        await _save_as_template(workspace, form, who)
    assert len(await _templates(workspace)) == 2


async def test_a_private_form_with_no_mode_counts_as_restricted(restricted, monkeypatch):
    workspace, form = restricted["workspace"], restricted["form"]
    # no mode chosen, form hidden: written with the switch off (a save keeps
    # the stored mode while it is on)
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    repo = container.workspace_form_repo()
    link = await repo.find_workspace_form(workspace.id, str(form.form_id))
    link.settings.access_mode = None
    link.settings.hidden = True
    await repo.save(link)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    await _refused(
        workspace, form, restricted["editor_grantee"], 403, TEMPLATE_FROM_RESTRICTED_CODE
    )
    await _save_as_template(workspace, form, restricted["creator"])
    await _save_as_template(workspace, form, restricted["admin"])


async def test_a_creator_who_is_no_longer_a_member_is_refused(restricted):
    workspace, form = restricted["workspace"], restricted["form"]
    members = container.workspace_user_repo()
    membership = await members.find_workspace_user(
        workspace.id, restricted["creator"].id
    )
    membership.disabled = True
    await members.save(membership)
    await _refused(workspace, form, restricted["creator"], 403)


async def test_with_the_switch_off_everyone_behaves_as_before(restricted, monkeypatch):
    workspace, form = restricted["workspace"], restricted["form"]
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    for who in (
        testUser,
        restricted["admin"],
        restricted["creator"],
        restricted["editor_grantee"],
        restricted["outsider"],
    ):
        await _save_as_template(workspace, form, who)
    assert len(await _templates(workspace)) == 5
    # a Viewer still cannot (the workspace permission, as before)
    await _refused(workspace, form, restricted["grantee"], 403)


async def test_the_endpoint_answers_403_with_the_code(client: AsyncClient, restricted):
    workspace, form = restricted["workspace"], restricted["form"]
    path = f"{api(workspace)}/form/{form.form_id}/template"
    refused = await client.post(path, cookies=cookies(restricted["editor_grantee"]))
    assert refused.status_code == 403
    assert refused.json() == {
        "code": TEMPLATE_FROM_RESTRICTED_CODE,
        "message": TEMPLATE_FROM_RESTRICTED_MESSAGE,
    }
    allowed = await client.post(path, cookies=cookies(restricted["creator"]))
    assert allowed.status_code == 200, allowed.text
    unknown = await client.post(
        f"{api(workspace)}/form/{RecordId()}/template",
        cookies=cookies(restricted["outsider"]),
    )
    closed = await client.post(path, cookies=cookies(restricted["outsider"]))
    assert closed.status_code == unknown.status_code == 404
