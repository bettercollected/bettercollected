"""The form-level decision through ``AuthorizationService``, against the real
tables: roles, grants (direct and through teams), restricted and Private forms,
the creator, Owners and Admins, a disabled membership or workspace, and the
sign-in rules that sit under all of it."""

import pytest
from common.ids import RecordId

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
)
from backend.app.services.authorization_service import (
    DISABLED_WORKSPACE_OWNER_PERMISSIONS,
    EDITOR_PERMISSIONS,
    VIEWER_PERMISSIONS,
    AuthorizationService,
)
from backend.app.services.form_access.model import (
    FORM_SCOPED,
    MODE_RESTRICTED,
    MODE_WORKSPACE,
    SOURCE_CREATOR,
    SOURCE_GRANT,
    SOURCE_NONE,
    SOURCE_ROLE,
)
from tests.app.controllers.data import invited_user, testUser
from tests.app.form_access.helpers import (
    add_member,
    create_form,
    grant,
    restrict,
    set_mode,
    team_with,
)

P = Permission


@pytest.fixture()
def authz():
    return container.authorization_service()


async def perms(authz, user, workspace, form):
    return await authz.effective_permissions(user, workspace.id, form_id=form.form_id)


async def refused(authz, user, permission, workspace, form):
    with pytest.raises(HTTPException) as error:
        await authz.authorize(user, permission, workspace.id, form_id=form.form_id)
    return error.value


# -- grants on an open form -------------------------------------------------------
async def test_a_grant_raises_a_viewer_on_that_form_only(
    switch_on, authz, workspace, workspace_form
):
    other = await create_form(workspace, testUser)
    viewer = await add_member(workspace, "VIEWER")
    assert P.FORM_EDIT not in await perms(authz, viewer, workspace, workspace_form)

    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)

    assert await authz.has_permission(
        viewer, P.FORM_EDIT, workspace.id, form_id=workspace_form.form_id
    )
    await authz.authorize(
        viewer, P.RESPONSE_ANNOTATE, workspace.id, form_id=workspace_form.form_id
    )
    # the other form, and the workspace as a whole, are as before
    assert P.FORM_EDIT not in await perms(authz, viewer, workspace, other)
    assert P.FORM_EDIT not in await authz.effective_permissions(viewer, workspace.id)
    assert (await refused(authz, viewer, P.FORM_EDIT, workspace, other)).status_code == 403


async def test_a_team_grant_reaches_the_teams_members_and_nobody_else(
    switch_on, authz, workspace, workspace_form
):
    inside = await add_member(workspace, "VIEWER")
    outside = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, inside)
    await grant(
        workspace, workspace_form.form_id, team.id, ROLE_REVIEWER, subject_type="group"
    )

    assert P.RESPONSE_ANNOTATE in await perms(authz, inside, workspace, workspace_form)
    assert P.RESPONSE_ANNOTATE not in await perms(authz, outside, workspace, workspace_form)


async def test_a_person_and_a_team_grant_take_the_union(
    switch_on, authz, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, viewer)
    await grant(
        workspace, workspace_form.form_id, team.id, ROLE_REVIEWER, subject_type="group"
    )
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_VIEWER, export=True)

    held = await perms(authz, viewer, workspace, workspace_form)
    assert P.RESPONSE_ANNOTATE in held  # from the team
    assert P.RESPONSE_EXPORT in held  # from the person's flag
    assert P.FORM_EDIT not in held


async def test_a_grant_never_gives_a_workspace_level_permission(
    switch_on, authz, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR, export=True)
    held = await perms(authz, viewer, workspace, workspace_form)
    assert held - VIEWER_PERMISSIONS <= FORM_SCOPED
    assert P.FORM_DELETE not in held
    assert P.PRIVACY_MANAGE not in held and P.FORM_CREATE not in held


async def test_grants_of_another_workspace_or_form_never_apply(
    switch_on, authz, workspace, workspace_form, workspace_1
):
    viewer = await add_member(workspace, "VIEWER")
    other_form = await create_form(workspace, testUser)
    # a grant on another form of this workspace
    await grant(workspace, other_form.form_id, viewer.id, ROLE_EDITOR)
    # a grant on this form, but stamped with another workspace
    await grant(
        workspace,
        workspace_form.form_id,
        viewer.id,
        ROLE_EDITOR,
        workspace_id=workspace_1.id,
        subject_type="user",
    )
    # and a subject type this code does not read for a person (API keys, later)
    await grant(
        workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR, subject_type="key"
    )
    assert P.FORM_EDIT not in await perms(authz, viewer, workspace, workspace_form)


async def test_a_team_of_another_workspace_does_not_reach_a_member_here(
    switch_on, authz, workspace, workspace_form, workspace_1
):
    viewer = await add_member(workspace, "VIEWER")
    foreign_team = await team_with(workspace_1, viewer, name="Foreign")
    await grant(
        workspace, workspace_form.form_id, foreign_team.id, ROLE_EDITOR, subject_type="group"
    )
    assert P.FORM_EDIT not in await perms(authz, viewer, workspace, workspace_form)


async def test_a_grant_to_a_user_id_does_not_match_a_team_with_that_id(
    switch_on, authz, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    await grant(
        workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR, subject_type="group"
    )
    assert P.FORM_EDIT not in await perms(authz, viewer, workspace, workspace_form)


# -- restricted forms ---------------------------------------------------------------
async def test_a_restricted_form_is_unknown_to_a_member_without_a_way_in(
    switch_on, authz, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    editor = await add_member(workspace, "COLLABORATOR")

    assert await perms(authz, editor, workspace, workspace_form) & FORM_SCOPED == frozenset()
    assert not await authz.has_permission(
        editor, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
    )
    # 404 with the message of an id that is not a form, whatever the permission
    for permission in (P.FORM_READ, P.RESPONSE_EXPORT, P.FORM_EDIT):
        error = await refused(authz, editor, permission, workspace, workspace_form)
        assert error.status_code == 404
        assert error.content == "Form not found in workspace"
    unknown = await authz.authorize(  # an unknown id keeps today's answer for them
        editor, P.FORM_CREATE, workspace.id, form_id=None
    )
    assert unknown is None
    with pytest.raises(HTTPException) as missing:
        await authz.authorize(
            editor, P.FORM_READ, workspace.id, form_id=str(RecordId())
        )
    assert (missing.value.status_code, missing.value.content) == (
        404,
        "Form not found in workspace",
    )


async def test_the_workspace_level_answer_is_not_closed_by_a_restricted_form(
    switch_on, authz, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    editor = await add_member(workspace, "COLLABORATOR")
    assert await authz.effective_permissions(editor, workspace.id) == EDITOR_PERMISSIONS


async def test_a_grant_opens_a_restricted_form_at_the_grants_role(
    switch_on, authz, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    editor = await add_member(workspace, "COLLABORATOR")
    await grant(workspace, workspace_form.form_id, editor.id, ROLE_VIEWER)

    held = await perms(authz, editor, workspace, workspace_form)
    assert held & FORM_SCOPED == {P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ}
    await authz.authorize(editor, P.RESPONSE_READ, workspace.id, form_id=workspace_form.form_id)
    # the Editor role's reach does not carry through: a Viewer grant is a Viewer
    assert (await refused(authz, editor, P.FORM_EDIT, workspace, workspace_form)).status_code == 403


async def test_a_team_grant_opens_a_restricted_form(
    switch_on, authz, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    viewer = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, viewer)
    await grant(workspace, workspace_form.form_id, team.id, ROLE_REVIEWER, subject_type="group")
    assert P.RESPONSE_ANNOTATE in await perms(authz, viewer, workspace, workspace_form)


async def test_owner_and_admin_always_pass_a_restricted_form(
    switch_on, authz, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    admin = await add_member(workspace, "ADMIN")
    second_owner = await add_member(workspace, "OWNER")
    for user in (testUser, admin, second_owner):
        await authz.authorize(user, P.FORM_EDIT, workspace.id, form_id=workspace_form.form_id)
        await authz.authorize(
            user, P.RESPONSE_EXPORT, workspace.id, form_id=workspace_form.form_id
        )
    decided = await authz.form_permissions(admin, workspace.id, workspace_form.form_id)
    assert decided.source == SOURCE_ROLE


async def test_the_creator_keeps_their_roles_permissions_on_a_restricted_form(
    switch_on, authz, workspace
):
    creator = await add_member(workspace, "COLLABORATOR")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)

    decided = await authz.form_permissions(creator, workspace.id, form.form_id)
    assert decided.permissions == EDITOR_PERMISSIONS
    assert decided.source == SOURCE_CREATOR
    # another Editor is shut out of the same form
    other = await add_member(workspace, "COLLABORATOR")
    assert (await authz.form_permissions(other, workspace.id, form.form_id)).source == SOURCE_NONE


async def test_a_demoted_creator_keeps_only_their_current_roles_rights(
    switch_on, authz, workspace
):
    creator = await add_member(workspace, "COLLABORATOR")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)
    # demoted to Viewer
    membership = await container.workspace_user_repo().find_workspace_user(
        workspace.id, RecordId(creator.id)
    )
    membership.roles = ["VIEWER"]
    await container.workspace_user_repo().save(membership)

    assert await perms(authz, creator, workspace, form) == VIEWER_PERMISSIONS


async def test_a_removed_creator_loses_the_creator_rule(switch_on, authz, workspace):
    creator = await add_member(workspace, "COLLABORATOR")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)
    membership = await container.workspace_user_repo().find_workspace_user(
        workspace.id, RecordId(creator.id)
    )
    membership.disabled = True
    await container.workspace_user_repo().save(membership)

    assert not await perms(authz, creator, workspace, form)


async def test_a_privacy_officer_keeps_structure_and_privacy_on_a_restricted_form(
    switch_on, authz, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    # a grant stored for them (it cannot be made through the API) is inert
    await grant(workspace, workspace_form.form_id, officer.id, ROLE_EDITOR, export=True)

    held = await perms(authz, officer, workspace, workspace_form)
    assert held == {P.FORM_READ, P.PRIVACY_MANAGE, P.AUDIT_READ}
    await authz.authorize(officer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id)


async def test_a_grant_does_not_elevate_a_privacy_officer_on_an_open_form(
    switch_on, authz, workspace, workspace_form
):
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    await grant(workspace, workspace_form.form_id, officer.id, ROLE_EDITOR, export=True)
    held = await perms(authz, officer, workspace, workspace_form)
    assert P.RESPONSE_READ not in held and P.FORM_EDIT not in held


# -- Private ("hidden") and the explicit mode -------------------------------------------
async def test_a_private_form_without_a_mode_counts_as_restricted(
    switch_on, authz, workspace, workspace_form
):
    await set_mode(workspace, workspace_form.form_id, hidden=True)
    editor = await add_member(workspace, "COLLABORATOR")
    assert (await refused(authz, editor, P.FORM_READ, workspace, workspace_form)).status_code == 404
    await authz.authorize(testUser, P.FORM_READ, workspace.id, form_id=workspace_form.form_id)


async def test_an_explicit_mode_beats_hidden(switch_on, authz, workspace, workspace_form):
    await set_mode(workspace, workspace_form.form_id, MODE_WORKSPACE, hidden=True)
    editor = await add_member(workspace, "COLLABORATOR")
    assert await perms(authz, editor, workspace, workspace_form) == EDITOR_PERMISSIONS


async def test_the_switch_off_ignores_hidden_and_the_mode_alike(
    switch_off, authz, workspace, workspace_form
):
    await set_mode(workspace, workspace_form.form_id, MODE_RESTRICTED, hidden=True)
    editor = await add_member(workspace, "COLLABORATOR")
    assert await perms(authz, editor, workspace, workspace_form) == EDITOR_PERMISSIONS


# -- what stays nothing --------------------------------------------------------------------
async def test_a_stranger_stays_nobody_even_with_a_grant_stored(
    switch_on, authz, workspace, workspace_form
):
    stranger = await add_member(workspace, "VIEWER")  # then removed below
    outsider = type(stranger)(id=str(RecordId()), sub="outsider@example.org")
    await grant(workspace, workspace_form.form_id, outsider.id, ROLE_EDITOR)
    assert not await perms(authz, outsider, workspace, workspace_form)
    # 403 (no membership), not the 404 of a closed form
    assert (await refused(authz, outsider, P.FORM_READ, workspace, workspace_form)).status_code == 403


async def test_a_disabled_membership_with_a_grant_holds_nothing(
    switch_on, authz, workspace, workspace_form
):
    disabled = await add_member(workspace, "VIEWER", disabled=True)
    await grant(workspace, workspace_form.form_id, disabled.id, ROLE_EDITOR)
    assert not await perms(authz, disabled, workspace, workspace_form)


async def test_a_disabled_workspace_is_not_opened_by_grants(
    switch_on, authz, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)
    workspace.disabled = True
    await container.workspace_repo().save(workspace)

    assert not await perms(authz, viewer, workspace, workspace_form)
    assert await perms(authz, testUser, workspace, workspace_form) == (
        DISABLED_WORKSPACE_OWNER_PERMISSIONS
    )


async def test_a_blocked_session_is_not_opened_by_a_grant(
    switch_on, authz, workspace, workspace_form, monkeypatch
):
    """Single sign-on and the authenticator-app rule sit under the grants: a
    session they block holds nothing, whatever is granted."""
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)
    assert P.FORM_EDIT in await perms(authz, viewer, workspace, workspace_form)

    async def blocked(self, user, workspace, is_owner):
        return True

    monkeypatch.setattr(AuthorizationService, "_sso_blocks", blocked)
    assert not await perms(authz, viewer, workspace, workspace_form)
    assert not await authz.has_permission(
        viewer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
    )


async def test_a_respondent_scoped_session_holds_nothing_on_a_form(
    switch_on, authz, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)
    respondent = viewer.model_copy(update={"session_scope": "respondent"})
    assert not await perms(authz, respondent, workspace, workspace_form)


async def test_an_unknown_role_holds_nothing_even_with_a_grant(
    switch_on, authz, workspace, workspace_form
):
    future = await add_member(workspace, "SOMETHING_NEW")
    await grant(workspace, workspace_form.form_id, future.id, ROLE_EDITOR)
    assert not await perms(authz, future, workspace, workspace_form)


async def test_a_form_of_another_workspace_decides_nothing(
    switch_on, authz, workspace, workspace_1, workspace_form_1
):
    """A form id that is not the workspace's keeps today's answer: the 404
    follows the permission check, and nothing about the other workspace's
    grants is read."""
    editor = await add_member(workspace, "COLLABORATOR")
    decided = await authz.form_permissions(editor, workspace.id, workspace_form_1.form_id)
    assert decided.permissions == EDITOR_PERMISSIONS and not decided.form_found
    error = await refused(authz, editor, P.FORM_EDIT, workspace, workspace_form_1)
    assert error.status_code == 404


async def test_the_form_found_flag_saves_the_second_lookup(
    switch_on, authz, workspace, workspace_form
):
    editor = await add_member(workspace, "COLLABORATOR")
    decided = await authz.form_permissions(editor, workspace.id, workspace_form.form_id)
    assert decided.form_found and decided.source == SOURCE_ROLE


async def test_source_says_where_the_permissions_came_from(
    switch_on, authz, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    assert (await authz.form_permissions(viewer, workspace.id, workspace_form.form_id)).source == SOURCE_ROLE
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)
    assert (await authz.form_permissions(viewer, workspace.id, workspace_form.form_id)).source == SOURCE_GRANT


# -- the list helpers --------------------------------------------------------------------------
async def test_visible_form_ids_and_the_filter(switch_on, authz, workspace, workspace_form):
    open_form = workspace_form
    closed = await create_form(workspace, testUser)
    granted = await create_form(workspace, testUser)
    own_creator = await add_member(workspace, "COLLABORATOR")
    own = await create_form(workspace, own_creator)
    for form in (closed, granted, own):
        await restrict(workspace, form.form_id)
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, granted.form_id, viewer.id, ROLE_VIEWER)

    ids = {f.form_id for f in (open_form, closed, granted, own)}
    seen = await authz.visible_form_ids(viewer, workspace.id, P.FORM_READ)
    assert seen == {open_form.form_id, granted.form_id}
    assert await authz.visible_form_ids(own_creator, workspace.id, P.FORM_READ) == {
        open_form.form_id,
        own.form_id,
    }
    # an Owner (and so an Admin) sees everything: None means "every form"
    assert await authz.visible_form_ids(testUser, workspace.id, P.FORM_READ) is None
    # a permission the grant does not give
    assert await authz.visible_form_ids(viewer, workspace.id, P.FORM_EDIT) == frozenset()
    # a stranger sees none
    outsider = type(viewer)(id=str(RecordId()), sub="o@example.org")
    assert await authz.visible_form_ids(outsider, workspace.id, P.FORM_READ) == frozenset()
    # given ids narrow it, and unknown ids are not forms
    narrowed = await authz.visible_form_ids(
        viewer, workspace.id, P.FORM_READ, [closed.form_id, granted.form_id, str(RecordId())]
    )
    assert narrowed == {granted.form_id}
    assert ids  # (all four exist)


async def test_the_form_access_filter_keeps_the_callers_order(
    switch_on, authz, workspace, workspace_form
):
    closed = await create_form(workspace, testUser)
    await restrict(workspace, closed.form_id)
    viewer = await add_member(workspace, "VIEWER")
    service = container.form_access_service()
    base = await authz._base_access(viewer, workspace.id)

    asked = [closed.form_id, workspace_form.form_id]
    assert await service.filter(base, asked, P.FORM_READ) == [workspace_form.form_id]
    assert await service.filter(base, reversed(asked), P.FORM_READ) == [workspace_form.form_id]


async def test_get_visible_link_answers_alike_for_unknown_and_closed(
    switch_on, authz, workspace, workspace_form
):
    closed = await create_form(workspace, testUser)
    await restrict(workspace, closed.form_id)
    viewer = await add_member(workspace, "VIEWER")
    service = container.form_access_service()
    base = await authz._base_access(viewer, workspace.id)

    assert await service.get_visible_link(base, closed.form_id) is None
    assert await service.get_visible_link(base, str(RecordId())) is None
    link = await service.get_visible_link(base, workspace_form.form_id)
    assert link is not None and link.form_id == workspace_form.form_id
    owner_base = await authz._base_access(testUser, workspace.id)
    assert (await service.get_visible_link(owner_base, closed.form_id)) is not None
    nobody = await authz._base_access(
        type(viewer)(id=str(RecordId()), sub="o@example.org"), workspace.id
    )
    assert await service.get_visible_link(nobody, workspace_form.form_id) is None


async def test_the_lists_follow_a_grant_the_moment_it_changes(
    switch_on, authz, workspace, workspace_form
):
    """No cross-request cache: a revoked grant is gone on the next call."""
    closed = await create_form(workspace, testUser)
    await restrict(workspace, closed.form_id)
    viewer = await add_member(workspace, "VIEWER")
    row = await grant(workspace, closed.form_id, viewer.id, ROLE_VIEWER)
    assert closed.form_id in await authz.visible_form_ids(viewer, workspace.id, P.FORM_READ)
    await container.form_access_grant_repo().delete(workspace.id, closed.form_id, row.id)
    assert closed.form_id not in await authz.visible_form_ids(viewer, workspace.id, P.FORM_READ)
    assert (await refused(authz, viewer, P.FORM_READ, workspace, closed)).status_code == 404


# -- the invited user of the shared fixtures, for good measure --------------------------------
async def test_the_shared_fixture_members_behave(switch_on, authz, workspace, workspace_form):
    # invited_user is an Editor of the fixture workspace
    assert await perms(authz, invited_user, workspace, workspace_form) == EDITOR_PERMISSIONS
    await restrict(workspace, workspace_form.form_id)
    assert not (await perms(authz, invited_user, workspace, workspace_form)) & FORM_SCOPED
