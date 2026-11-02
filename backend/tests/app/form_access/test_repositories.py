"""The grant and member-group repositories: workspace scoping, one row per
relation, the unique team name, cascades the repositories own."""

import pytest
from common.ids import RecordId
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_VIEWER,
    FormAccessGrantDocument,
)
from backend.app.schemas.member_group import MemberGroupDocument, name_key
from tests.app.form_access.helpers import add_member, grant, team_with


@pytest.fixture()
def grants():
    return container.form_access_grant_repo()


@pytest.fixture()
def teams():
    return container.member_group_repo()


def uid():
    return str(RecordId())


# -- grants ---------------------------------------------------------------------------
async def test_a_second_grant_to_the_same_subject_is_the_same_row(workspace, grants):
    form_id = uid()
    first = await grant(workspace, form_id, "u1", ROLE_VIEWER)
    second = await grant(workspace, form_id, "u1", ROLE_EDITOR, export=True)

    assert first.id == second.id
    rows = await grants.list_for_form(workspace.id, form_id)
    assert len(rows) == 1 and rows[0].role == ROLE_EDITOR and rows[0].export
    # another subject, another form: other rows
    await grant(workspace, form_id, "u2", ROLE_VIEWER)
    await grant(workspace, uid(), "u1", ROLE_VIEWER)
    assert len(await grants.list_for_form(workspace.id, form_id)) == 2


async def test_the_subject_type_is_part_of_the_key(workspace, grants):
    form_id = uid()
    await grant(workspace, form_id, "x1", ROLE_VIEWER, subject_type="user")
    await grant(workspace, form_id, "x1", ROLE_VIEWER, subject_type="group")
    await grant(workspace, form_id, "x1", ROLE_VIEWER, subject_type="key")
    assert len(await grants.list_for_form(workspace.id, form_id)) == 3


async def test_the_table_refuses_a_duplicate_the_repository_did_not_derive(workspace):
    """The unique (form, subject_type, subject_id) holds in the table itself."""
    form_id = uid()
    await grant(workspace, form_id, "u1", ROLE_VIEWER)
    with pytest.raises(IntegrityError):
        await container.form_access_grant_repo().save_document(
            FormAccessGrantDocument(
                workspace_id=workspace.id,
                form_id=form_id,
                subject_type="user",
                subject_id="u1",
                role=ROLE_EDITOR,
            )
        )


async def test_lookups_carry_the_workspace_and_the_form(workspace, workspace_1, grants):
    form_id = uid()
    row = await grant(workspace, form_id, "u1", ROLE_VIEWER)

    assert await grants.find(workspace.id, form_id, row.id) is not None
    assert await grants.find(workspace_1.id, form_id, row.id) is None
    assert await grants.find(workspace.id, uid(), row.id) is None
    assert await grants.list_for_form(workspace_1.id, form_id) == []

    # a delete under the wrong workspace or form deletes nothing
    assert not await grants.delete(workspace_1.id, form_id, row.id)
    assert not await grants.delete(workspace.id, uid(), row.id)
    assert await grants.delete(workspace.id, form_id, row.id)
    assert await grants.find(workspace.id, form_id, row.id) is None


async def test_a_users_grants_include_their_teams_in_one_workspace(
    workspace, workspace_1, grants
):
    user = await add_member(workspace, "VIEWER")
    form_a, form_b, form_c = uid(), uid(), uid()
    team = await team_with(workspace, user)
    other_team = await team_with(workspace, name="Others")
    await grant(workspace, form_a, user.id, ROLE_VIEWER)
    await grant(workspace, form_b, team.id, ROLE_VIEWER, subject_type="group")
    await grant(workspace, form_c, other_team.id, ROLE_VIEWER, subject_type="group")

    held = await grants.for_user(workspace.id, user.id)
    assert {g.form_id for g in held} == {form_a, form_b}
    assert {g.form_id for g in await grants.for_user(workspace.id, user.id, [form_a])} == {form_a}
    assert await grants.for_user(workspace.id, user.id, []) == []
    assert await grants.for_user(workspace_1.id, user.id) == []
    on_b = await grants.for_user_on_form(workspace.id, form_b, user.id)
    assert [g.subject_id for g in on_b] == [str(team.id)]
    assert await grants.for_user_on_form(workspace.id, form_c, user.id) == []


async def test_deleting_by_form_and_by_subject(workspace, workspace_1, grants):
    form_a, form_b = uid(), uid()
    await grant(workspace, form_a, "u1", ROLE_VIEWER)
    await grant(workspace, form_a, "u2", ROLE_VIEWER)
    await grant(workspace, form_b, "u1", ROLE_VIEWER)
    await grant(workspace_1, form_a, "u1", ROLE_VIEWER)

    assert await grants.delete_for_subject(workspace.id, "user", "u1") == 2
    assert [g.subject_id for g in await grants.list_for_form(workspace.id, form_a)] == ["u2"]
    assert await grants.delete_for_form(workspace.id, form_a) == 1
    assert len(await grants.list_for_form(workspace_1.id, form_a)) == 1  # untouched


# -- teams --------------------------------------------------------------------------------
async def test_team_names_are_unique_per_workspace_ignoring_case_and_blanks(
    workspace, workspace_1, teams
):
    await teams.save(MemberGroupDocument(workspace_id=workspace.id, name="Human Resources"))
    assert name_key("  human   RESOURCES ") == name_key("Human Resources")
    with pytest.raises(IntegrityError):
        await teams.save(
            MemberGroupDocument(workspace_id=workspace.id, name="  human   RESOURCES ")
        )
    # another workspace may use the name
    await teams.save(MemberGroupDocument(workspace_id=workspace_1.id, name="Human Resources"))
    found = await teams.find_by_name(workspace.id, "HUMAN resources")
    assert found is not None and found.name == "Human Resources"
    assert await teams.find_by_name(workspace_1.id, "nobody") is None
    assert len(await teams.list_in_workspace(workspace.id)) == 1


async def test_adding_a_member_twice_is_one_row(workspace, teams):
    user = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, user)
    await teams.add_member(workspace.id, team.id, user.id)
    assert await teams.member_ids(workspace.id, team.id) == [user.id]
    assert await teams.group_ids_of(workspace.id, user.id) == [str(team.id)]


async def test_membership_is_scoped_to_the_workspace(workspace, workspace_1, teams):
    user = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, user)
    assert await teams.group_ids_of(workspace_1.id, user.id) == []
    assert await teams.member_ids(workspace_1.id, team.id) == []
    assert await teams.find(workspace_1.id, team.id) is None
    assert await teams.remove_member(workspace_1.id, team.id, user.id) == 0
    assert await teams.remove_member(workspace.id, team.id, user.id) == 1
    assert await teams.group_ids_of(workspace.id, user.id) == []


async def test_deleting_a_team_deletes_its_members_and_nothing_else(
    workspace, workspace_1, teams
):
    first, second = await add_member(workspace, "VIEWER"), await add_member(workspace, "VIEWER")
    team = await team_with(workspace, first, second, name="A")
    keep = await team_with(workspace, first, name="B")

    assert not await teams.delete(workspace_1.id, team.id)  # wrong workspace
    assert await teams.member_ids(workspace.id, team.id) == [first.id, second.id]
    assert await teams.delete(workspace.id, team.id)
    assert await teams.find(workspace.id, team.id) is None
    assert await teams.member_ids(workspace.id, team.id) == []
    assert await teams.group_ids_of(workspace.id, first.id) == [str(keep.id)]
    assert not await teams.delete(workspace.id, team.id)
