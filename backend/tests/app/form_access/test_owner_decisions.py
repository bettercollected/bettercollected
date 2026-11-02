"""Two decisions the owner took about form-level access, pinned.

1. Export through a grant (decided): an Editor grant INCLUDES export, as the
   Editor role does; a Reviewer or Viewer grant exports only with the export flag
   (which only an Owner or an Admin sets). Pinned as ordinary assertions.

2. A template of a restricted form (decided and built): a template is a
   deliberate copy of a form's structure into the workspace library, readable by
   every member, so on a restricted form with the switch on only an Owner, an
   Admin or the form's creator may save one. Anyone else with form.create (an
   Editor, an Editor grant included) gets 403 ``template_from_restricted_form``; a
   Viewer holding an Editor grant lacks form.create and gets the plain 403; a
   member the form is closed to gets the 404 of an unknown form; a creator whose
   membership is disabled is refused. Asserted on the code, not on the generic body.
"""

import pytest
from common.ids import RecordId
from common.models.standard_form import StandardFormResponse
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.form_access_grant import ROLE_EDITOR, ROLE_REVIEWER, ROLE_VIEWER
from backend.config import settings
from tests.app.controllers.data import formResponse, testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    cookies,
    create_form,
    grant,
    restrict,
)

from backend.app.services.form_access.mode import (  # noqa: E402
    TEMPLATE_FROM_RESTRICTED_CODE,
    TEMPLATE_FROM_RESTRICTED_MESSAGE,
)


@pytest.fixture()
async def restricted(workspace, monkeypatch):
    """A published restricted form, switch on."""
    form = await create_form(workspace, testUser)
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    await restrict(workspace, form.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    return form


# -- export through a grant (decided) ---------------------------------------------------


async def test_an_editor_grant_includes_export_and_reviewer_and_viewer_grants_need_the_flag(
    client: AsyncClient, workspace, restricted
):
    """``GET .../all-submissions`` is the bulk read (response.export), ``POST
    .../exports`` the file: both follow the grant."""
    await container.workspace_form_service().submit_response(
        workspace.id,
        restricted.form_id,
        StandardFormResponse(**formResponse),
        testUser,
    )
    url = f"{api(workspace)}/forms/{restricted.form_id}/all-submissions"
    cases = [
        (ROLE_EDITOR, False, 200),
        (ROLE_REVIEWER, False, 403),
        (ROLE_REVIEWER, True, 200),
        (ROLE_VIEWER, False, 403),
        (ROLE_VIEWER, True, 200),
    ]
    for role, export, want in cases:
        member = await add_member(workspace, "VIEWER")
        await grant(workspace, restricted.form_id, member.id, role, export=export)
        got = await client.get(url, cookies=cookies(member))
        assert got.status_code == want, (role, export, got.status_code, got.text[:100])
        if want == 200:
            assert len(got.json()) == 1, (role, export)  # the one answer, as data
    # the same with the file: the export of answers a member may export
    for role, export, want in cases:
        member = await add_member(workspace, "VIEWER")
        await grant(workspace, restricted.form_id, member.id, role, export=export)
        made = await client.post(
            f"{api(workspace)}/forms/{restricted.form_id}/exports",
            json={},
            cookies=cookies(member),
        )
        assert (made.status_code in (200, 201, 202)) is (want == 200), (
            role,
            export,
            made.status_code,
        )


# -- a template of a restricted form (decided; refusal not built yet) -------------------


async def _template(client, workspace, form_id, user):
    return await client.post(
        f"{api(workspace)}/form/{form_id}/template", cookies=cookies(user)
    )


async def test_an_owner_an_admin_and_the_creator_may_save_a_restricted_form_as_a_template(
    client: AsyncClient, workspace, monkeypatch
):
    creator = await add_member(workspace, "COLLABORATOR")
    admin = await add_member(workspace, "ADMIN")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    for user in (testUser, admin, creator):
        made = await _template(client, workspace, form.form_id, user)
        assert made.status_code == 200, (user.sub, made.status_code, made.text[:120])


async def test_a_viewer_with_an_editor_grant_and_a_closed_out_editor_are_refused_a_template_as_before(
    client: AsyncClient, workspace, restricted
):
    """A Viewer holding an Editor grant lacks form.create: the plain 403, whatever
    the restricted-form rule says; a member the form is closed to gets the 404 of
    an unknown form."""
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, restricted.form_id, viewer.id, ROLE_EDITOR)
    got = await _template(client, workspace, restricted.form_id, viewer)
    assert got.status_code == 403 and TEMPLATE_FROM_RESTRICTED_CODE not in got.text, got.text[:120]
    outsider = await add_member(workspace, "COLLABORATOR")
    closed = await _template(client, workspace, restricted.form_id, outsider)
    unknown = await _template(client, workspace, str(RecordId()), outsider)
    assert (closed.status_code, closed.text) == (unknown.status_code, unknown.text)
    assert closed.status_code == 404


async def test_a_creator_whose_membership_is_disabled_may_not_save_a_template(
    client: AsyncClient, workspace, monkeypatch
):
    creator = await add_member(workspace, "COLLABORATOR")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)
    repo = container.workspace_user_repo()
    membership = await repo.find_workspace_user(workspace.id, RecordId(creator.id))
    membership.disabled = True
    await repo.save(membership)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    got = await _template(client, workspace, form.form_id, creator)
    assert got.status_code in (403, 404), got.text[:120]


async def test_an_editor_who_did_not_create_a_restricted_form_may_not_save_it_as_a_template(
    client: AsyncClient, workspace, restricted
):
    """An Editor grant, and an Editor who holds the form through no grant at all
    (the form is theirs to open by being the creator only): the refusal is the
    code, not the generic 403 body."""
    editor = await add_member(workspace, "COLLABORATOR")
    await grant(workspace, restricted.form_id, editor.id, ROLE_EDITOR)
    got = await _template(client, workspace, restricted.form_id, editor)
    assert got.status_code == 403, (got.status_code, got.text[:120])
    assert got.json()["code"] == TEMPLATE_FROM_RESTRICTED_CODE, got.text[:150]
    assert got.json()["message"] == TEMPLATE_FROM_RESTRICTED_MESSAGE


async def test_the_template_rule_is_only_for_restricted_forms_with_the_switch_on(
    client: AsyncClient, workspace, restricted, monkeypatch
):
    editor = await add_member(workspace, "COLLABORATOR")
    await grant(workspace, restricted.form_id, editor.id, ROLE_EDITOR)
    open_form = await create_form(workspace, testUser)
    # an open form: any Editor may, as before
    assert (await _template(client, workspace, open_form.form_id, editor)).status_code == 200
    # the switch off: nothing is decided on the form
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    assert (
        await _template(client, workspace, restricted.form_id, editor)
    ).status_code == 200
