"""The writes themselves keep a team and a grant inside their workspace, whatever
the caller checked before (the repositories, called directly)."""

import pytest

from backend.app.container import container
from backend.app.repositories.postgres.form_access import AccessTargetNotFound
from backend.app.repositories.postgres.member_groups import TeamFull
from backend.app.schemas.form_access_grant import FormAccessGrantDocument
from backend.app.schemas.member_group import MemberGroupDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import add_member, create_form

pytestmark = pytest.mark.asyncio


def doc(workspace, form_id, subject_id, subject_type="user", role="VIEWER"):
    return FormAccessGrantDocument(
        workspace_id=workspace.id,
        form_id=str(form_id),
        subject_type=subject_type,
        subject_id=str(subject_id),
        role=role,
    )


async def test_a_grant_is_stored_for_a_form_and_a_member_of_the_workspace(
    workspace, workspace_form
):
    person = await add_member(workspace, "VIEWER")
    saved = await container.form_access_grant_repo().put(
        doc(workspace, workspace_form.form_id, person.id)
    )
    assert saved.id
    # a disabled member may hold one (it does nothing until they are enabled)
    disabled = await add_member(workspace, "VIEWER", disabled=True)
    await container.form_access_grant_repo().put(
        doc(workspace, workspace_form.form_id, disabled.id)
    )


async def test_a_grant_for_a_form_that_is_not_linked_to_the_workspace_is_refused(
    workspace, workspace_1, workspace_form
):
    person = await add_member(workspace, "VIEWER")
    repo = container.form_access_grant_repo()
    with pytest.raises(AccessTargetNotFound) as refused:
        await repo.put(doc(workspace, "f" * 24, person.id))
    assert refused.value.what == "form"
    # a real form, linked to another workspace only
    foreign = await create_form(workspace_1, testUser1)
    with pytest.raises(AccessTargetNotFound):
        await repo.put(doc(workspace, foreign.form_id, person.id))
    assert await repo.list_for_form(workspace.id, foreign.form_id) == []


async def test_a_grant_to_someone_who_is_not_a_member_is_refused(
    workspace, workspace_1, workspace_form
):
    outsider = await add_member(workspace_1, "VIEWER")
    repo = container.form_access_grant_repo()
    with pytest.raises(AccessTargetNotFound) as refused:
        await repo.put(doc(workspace, workspace_form.form_id, outsider.id))
    assert refused.value.what == "member"
    # a membership that was removed
    gone = await add_member(workspace, "VIEWER")
    await container.workspace_user_repo().delete(workspace.id, gone.id)
    with pytest.raises(AccessTargetNotFound):
        await repo.put(doc(workspace, workspace_form.form_id, gone.id))
    assert await repo.list_for_form(workspace.id, workspace_form.form_id) == []


async def test_a_grant_to_a_team_of_another_workspace_or_an_unknown_kind_is_refused(
    workspace, workspace_1, workspace_form
):
    foreign = await container.member_group_repo().save(
        MemberGroupDocument(workspace_id=workspace_1.id, name="Foreign")
    )
    own = await container.member_group_repo().save(
        MemberGroupDocument(workspace_id=workspace.id, name="Own")
    )
    repo = container.form_access_grant_repo()
    with pytest.raises(AccessTargetNotFound) as refused:
        await repo.put(doc(workspace, workspace_form.form_id, foreign.id, "group"))
    assert refused.value.what == "group"
    with pytest.raises(AccessTargetNotFound):
        await repo.put(doc(workspace, workspace_form.form_id, own.id, "key"))
    await repo.put(doc(workspace, workspace_form.form_id, own.id, "group"))
    assert len(await repo.list_for_form(workspace.id, workspace_form.form_id)) == 1


async def test_a_team_takes_only_active_members_of_its_own_workspace(
    workspace, workspace_1
):
    repo = container.member_group_repo()
    team = await repo.save(MemberGroupDocument(workspace_id=workspace.id, name="Own"))
    foreign = await repo.save(MemberGroupDocument(workspace_id=workspace_1.id, name="Far"))
    member = await add_member(workspace, "VIEWER")
    outsider = await add_member(workspace_1, "VIEWER")
    disabled = await add_member(workspace, "VIEWER", disabled=True)

    await repo.add_member(workspace.id, team.id, member.id)
    for user in (outsider, disabled):
        with pytest.raises(AccessTargetNotFound) as refused:
            await repo.add_member(workspace.id, team.id, user.id)
        assert refused.value.what == "member"
    # the team of another workspace, named with this workspace's id and the
    # other way round
    with pytest.raises(AccessTargetNotFound) as refused:
        await repo.add_member(workspace.id, foreign.id, member.id)
    assert refused.value.what == "group"
    with pytest.raises(AccessTargetNotFound):
        await repo.add_member(workspace_1.id, team.id, outsider.id)
    assert await repo.member_ids(workspace.id, team.id) == [member.id]
    assert await repo.member_ids(workspace_1.id, foreign.id) == []


async def test_a_team_has_a_size_limit_that_counts_distinct_members(workspace):
    repo = container.member_group_repo()
    team = await repo.save(MemberGroupDocument(workspace_id=workspace.id, name="Own"))
    first, second = await add_member(workspace, "VIEWER"), await add_member(workspace, "VIEWER")
    await repo.add_member(workspace.id, team.id, first.id, max_members=1)
    await repo.add_member(workspace.id, team.id, first.id, max_members=1)
    with pytest.raises(TeamFull):
        await repo.add_member(workspace.id, team.id, second.id, max_members=1)


async def test_the_mode_has_one_writer_that_keeps_the_rest_of_the_settings(
    workspace, workspace_form
):
    repo = container.workspace_form_repo()
    before = await repo.find_workspace_form(workspace.id, workspace_form.form_id)
    previous = await repo.set_access_mode(workspace.id, workspace_form.form_id, "restricted")
    assert previous is None
    after = await repo.find_workspace_form(workspace.id, workspace_form.form_id)
    assert after.settings.access_mode == "restricted"
    assert after.settings.model_copy(update={"access_mode": None}) == (
        before.settings.model_copy(update={"access_mode": None})
    )
    assert await repo.set_access_mode(workspace.id, workspace_form.form_id, "workspace") == (
        "restricted"
    )
    from backend.app.exceptions import HTTPException

    with pytest.raises(HTTPException) as unknown:
        await repo.set_access_mode(workspace.id, "e" * 24, "restricted")
    assert unknown.value.status_code == 404


async def test_removing_a_membership_row_directly_is_what_the_write_check_looks_at(workspace):
    """The check reads the live membership: a member removed after the team was
    built cannot be added again."""
    repo = container.member_group_repo()
    team = await repo.save(MemberGroupDocument(workspace_id=workspace.id, name="Own"))
    person = await add_member(workspace, "VIEWER")
    await container.workspace_user_repo().delete(workspace.id, person.id)
    with pytest.raises(AccessTargetNotFound):
        await repo.add_member(workspace.id, team.id, person.id)
    assert isinstance(
        await container.workspace_user_repo().find_workspace_user(workspace.id, testUser.id),
        WorkspaceUserDocument,
    )
