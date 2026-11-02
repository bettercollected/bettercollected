"""What happens to grants and team memberships when what they name goes away,
and what removing a member does to the workspace's forms.

Cleanup runs whatever the switch says (stored rows are never left to come back
to life); the forms-stay fix of member removal is not behind the switch at all."""

from unittest.mock import patch

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_audit_event import (
    ACCESS_MEMBER_PURGED,
    FORM_CREATOR_REASSIGNED,
    TEAM_DELETED,
)
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import workspace_service
from backend.config import settings
from common.models.standard_form import StandardFormResponse
from tests.app.controllers.data import formResponse, testUser, testUser1
from tests.app.form_access.helpers import restrict
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    create_form,
    fail_audit,
    grant,
    team_with,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(params=["on", "off"])
def either_switch(request, monkeypatch):
    monkeypatch.setattr(settings.form_access, "ENABLED", request.param == "on")
    return request.param


@pytest.fixture()
def auth_lookup():
    """The auth service's user lookup, which removing a member calls."""

    async def get(*args, **kwargs):
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in ids]}

    with patch("common.services.http_client.HttpClient.get", side_effect=get):
        yield


@pytest.fixture()
def no_storage(monkeypatch):
    monkeypatch.setattr(
        container.aws_service(), "delete_folder_from_s3", lambda *a, **k: None
    )


async def grants_of(workspace, form):
    return await container.form_access_grant_repo().list_for_form(
        workspace.id, form.form_id
    )


async def remove(client, workspace, member, by=testUser):
    return await client.delete(
        f"{api(workspace)}/members/{member.id}", cookies=cookies(by)
    )


# -- a form ----------------------------------------------------------------------
async def test_deleting_a_form_drops_its_grants_and_only_its_own(
    workspace, workspace_form, either_switch
):
    person = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, person, name="Team")
    other = await create_form(workspace, testUser)
    for form in (workspace_form, other):
        await grant(workspace, form.form_id, person.id, "VIEWER")
        await grant(workspace, form.form_id, team.id, "REVIEWER", subject_type="group")

    await container.workspace_form_service().delete_form_from_workspace(
        workspace.id, workspace_form.form_id, testUser
    )

    assert await grants_of(workspace, workspace_form) == []
    assert len(await grants_of(workspace, other)) == 2
    # the team and its member are not touched by a form going away
    assert await container.member_group_repo().member_ids(workspace.id, team.id) == [person.id]


async def test_a_form_shared_with_another_workspace_keeps_that_workspaces_grants(
    workspace, workspace_1, workspace_form, either_switch
):
    await container.workspace_form_repo().save(
        WorkspaceFormDocument(
            id=RecordId(),
            workspace_id=workspace_1.id,
            form_id=workspace_form.form_id,
            user_id=testUser1.id,
        )
    )
    here = await add_member(workspace, "VIEWER")
    there = await add_member(workspace_1, "VIEWER")
    await grant(workspace, workspace_form.form_id, here.id, "VIEWER")
    await grant(workspace_1, workspace_form.form_id, there.id, "VIEWER")

    await container.workspace_form_service().delete_form_from_workspace(
        workspace.id, workspace_form.form_id, testUser
    )

    assert await grants_of(workspace, workspace_form) == []
    assert len(await grants_of(workspace_1, workspace_form)) == 1


# -- a team --------------------------------------------------------------------------
async def test_deleting_a_team_drops_its_grants_and_its_members(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, person, name="Doomed")
    keep = await team_with(workspace, person, name="Keep")
    await grant(workspace, workspace_form.form_id, team.id, "EDITOR", subject_type="group")
    await grant(workspace, workspace_form.form_id, keep.id, "VIEWER", subject_type="group")
    await grant(workspace, workspace_form.form_id, person.id, "VIEWER")

    response = await client.delete(
        f"{api(workspace)}/member-groups/{team.id}", cookies=cookies(testUser)
    )
    assert response.status_code == 204

    remaining = {(g.subject_type, g.subject_id) for g in await grants_of(workspace, workspace_form)}
    assert remaining == {("group", str(keep.id)), ("user", person.id)}
    repo = container.member_group_repo()
    assert await repo.member_ids(workspace.id, team.id) == []
    assert await repo.member_ids(workspace.id, keep.id) == [person.id]
    (event,) = await audit_events(workspace, TEAM_DELETED)
    assert event.group_id == str(team.id) and event.count == 1


# -- a member -----------------------------------------------------------------------------
async def test_removing_a_member_keeps_the_forms_they_created(
    client: AsyncClient, workspace, auth_lookup, either_switch
):
    """The data-loss fix: it used to delete every form with the member's id on
    it. Not behind the switch."""
    creator = await add_member(workspace, "COLLABORATOR")
    theirs = await create_form(workspace, creator)
    ours = await create_form(workspace, testUser)

    response = await remove(client, workspace, creator)

    assert response.status_code == 200, response.text
    assert await container.workspace_user_repo().find_workspace_user(
        workspace.id, creator.id
    ) is None
    links = await container.workspace_form_repo().list_in_workspace(workspace.id)
    assert {str(link.form_id) for link in links} >= {theirs.form_id, ours.form_id}
    assert await container.form_service().get_form_document_by_id(theirs.form_id) is not None
    # the form is still the workspace's: its owner reaches it
    assert await container.authorization_service().has_permission(
        testUser, Permission.FORM_READ, workspace.id, form_id=theirs.form_id
    )


async def test_removing_a_member_drops_their_grants_and_teams_and_records_it(
    client: AsyncClient, workspace, workspace_form, auth_lookup, either_switch
):
    person = await add_member(workspace, "VIEWER")
    bystander = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, person, bystander, name="Team")
    other_team = await team_with(workspace, person, name="Other")
    await grant(workspace, workspace_form.form_id, person.id, "EDITOR")
    await grant(workspace, workspace_form.form_id, bystander.id, "VIEWER")
    await grant(workspace, workspace_form.form_id, team.id, "REVIEWER", subject_type="group")

    response = await remove(client, workspace, person)
    assert response.status_code == 200, response.text

    remaining = {(g.subject_type, g.subject_id) for g in await grants_of(workspace, workspace_form)}
    assert remaining == {("user", bystander.id), ("group", str(team.id))}
    repo = container.member_group_repo()
    assert await repo.member_ids(workspace.id, team.id) == [bystander.id]
    assert await repo.member_ids(workspace.id, other_team.id) == []
    (event,) = await audit_events(workspace, ACCESS_MEMBER_PURGED)
    # one grant and two team memberships
    assert (event.target_user_id, event.count, event.user_id) == (person.id, 3, testUser.id)

    # invited again later, they start with nothing
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=person.id, roles=["VIEWER"])
    )
    assert await container.form_access_grant_repo().direct_for_user(workspace.id, person.id) == []
    assert await repo.group_ids_of(workspace.id, person.id) == []


async def test_a_removal_with_nothing_held_writes_no_entry_and_needs_no_audit(
    client: AsyncClient, workspace, auth_lookup, switch_on, monkeypatch
):
    person = await add_member(workspace, "VIEWER")
    fail_audit(monkeypatch)
    response = await remove(client, workspace, person)
    assert response.status_code == 200, response.text


async def test_a_removal_that_would_drop_grants_is_not_made_unrecorded(
    client: AsyncClient, workspace, workspace_form, auth_lookup, switch_on, monkeypatch
):
    person = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, person.id, "VIEWER")
    fail_audit(monkeypatch)
    response = await remove(client, workspace, person)
    assert response.status_code == 503
    assert response.json()["code"] == "audit_unavailable"
    assert await container.workspace_user_repo().find_workspace_user(
        workspace.id, person.id
    ) is not None
    assert len(await grants_of(workspace, workspace_form)) == 1


async def test_removing_a_member_hands_their_forms_to_the_billing_owner_and_records_it(
    client: AsyncClient, workspace, auth_lookup, either_switch
):
    creator = await add_member(workspace, "COLLABORATOR")
    first = await create_form(workspace, creator)
    second = await create_form(workspace, creator)
    ours = await create_form(workspace, testUser)

    response = await remove(client, workspace, creator)
    assert response.status_code == 200, response.text

    links = {
        link.form_id: link.user_id
        for link in await container.workspace_form_repo().list_in_workspace(workspace.id)
    }
    assert links[first.form_id] == links[second.form_id] == str(workspace.owner_id)
    assert links[ours.form_id] == testUser.id
    events = await audit_events(workspace, FORM_CREATOR_REASSIGNED)
    assert sorted(e.form_id for e in events) == sorted([first.form_id, second.form_id])
    assert {(e.target_user_id, e.to_user_id, e.user_id) for e in events} == {
        (creator.id, str(workspace.owner_id), testUser.id)
    }
    assert "@" not in str([e.model_dump(mode="json") for e in events])


async def test_a_removal_that_cannot_be_recorded_changes_nothing(
    client: AsyncClient, workspace, auth_lookup, switch_on, monkeypatch
):
    creator = await add_member(workspace, "COLLABORATOR")
    theirs = await create_form(workspace, creator)
    fail_audit(monkeypatch)
    response = await remove(client, workspace, creator)
    assert response.status_code == 503
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, theirs.form_id
    )
    assert link.user_id == creator.id
    assert await container.workspace_user_repo().find_workspace_user(
        workspace.id, creator.id
    ) is not None


async def test_the_removal_is_one_transaction(
    client: AsyncClient, workspace, workspace_form, auth_lookup, switch_on, monkeypatch
):
    """When a step fails the member, their forms and their grants are all as
    they were."""
    creator = await add_member(workspace, "COLLABORATOR")
    theirs = await create_form(workspace, creator)
    await grant(workspace, workspace_form.form_id, creator.id, "EDITOR")
    team = await team_with(workspace, creator, name="Team")

    removal = container.member_removal_repo()
    real = removal._delete_recorded
    seen = []

    async def failing(session, row, *where):
        seen.append(row.__tablename__)
        if row.__tablename__ == "member_group_members":
            raise RuntimeError("boom")
        return await real(session, row, *where)

    monkeypatch.setattr(removal, "_delete_recorded", failing)
    with pytest.raises(RuntimeError):
        await removal.remove(workspace.id, creator.id, str(workspace.owner_id))

    assert "member_group_members" in seen
    assert await container.workspace_user_repo().find_workspace_user(
        workspace.id, creator.id
    ) is not None
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, theirs.form_id
    )
    assert link.user_id == creator.id
    assert len(await grants_of(workspace, workspace_form)) == 1
    assert await container.member_group_repo().member_ids(workspace.id, team.id) == [creator.id]


async def test_a_removed_creator_who_deletes_their_account_does_not_take_the_forms_with_them(
    client: AsyncClient, workspace, auth_lookup, no_storage, either_switch
):
    leaving = User(id=str(RecordId()), sub=f"{RecordId()}@example.org")
    await workspace_service.create_workspace(leaving)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=leaving.id, roles=["COLLABORATOR"]
        )
    )
    theirs = await create_form(workspace, leaving)
    published = await container.workspace_form_service().publish_form(
        workspace.id, theirs.form_id, testUser
    )
    await container.workspace_form_service().submit_response(
        workspace.id, published.form_id, StandardFormResponse(**formResponse), testUser
    )
    assert await container.form_response_service().get_responses_count_in_workspace(
        workspace.id, [theirs.form_id]
    ) == 1

    assert (await remove(client, workspace, leaving)).status_code == 200
    await container.workspace_service().delete_workspaces_of_user_with_forms(leaving)

    assert await container.workspace_form_repo().find_workspace_form(
        workspace.id, theirs.form_id
    ) is not None
    assert await container.form_service().get_form_document_by_id(theirs.form_id) is not None
    assert await container.form_response_service().get_responses_count_in_workspace(
        workspace.id, [theirs.form_id]
    ) == 1


async def test_a_removed_creator_who_is_invited_again_has_no_creator_rights(
    client: AsyncClient, workspace, auth_lookup, switch_on
):
    creator = await add_member(workspace, "COLLABORATOR")
    theirs = await create_form(workspace, creator)
    await restrict(workspace, theirs.form_id)
    authz = container.authorization_service()
    assert Permission.FORM_EDIT in await authz.effective_permissions(
        creator, workspace.id, form_id=theirs.form_id
    )

    assert (await remove(client, workspace, creator)).status_code == 200
    # invited again, even as an editor again
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=creator.id, roles=["COLLABORATOR"]
        )
    )

    assert Permission.FORM_EDIT not in await authz.effective_permissions(
        creator, workspace.id, form_id=theirs.form_id
    )
    assert not await authz.has_permission(
        creator, Permission.FORM_READ, workspace.id, form_id=theirs.form_id
    )
    # and the mode is not theirs to change
    changed = await client.put(
        f"{api(workspace)}/forms/{theirs.form_id}/access/mode",
        cookies=cookies(creator),
        json={"mode": "workspace"},
    )
    assert changed.status_code == 404
    # the workspace's owner still reaches it
    assert await authz.has_permission(
        testUser, Permission.FORM_READ, workspace.id, form_id=theirs.form_id
    )


# -- an account and a workspace ----------------------------------------------------------------
async def test_deleting_an_account_drops_its_grants_and_teams_and_its_own_workspace_data(
    workspace, workspace_form, no_storage, either_switch
):
    leaving = User(id=str(RecordId()), sub=f"{RecordId()}@example.org")
    await workspace_service.create_workspace(leaving)
    own = await container.workspace_repo().get_default_workspace_by_owner_id(leaving.id)
    own_form = await create_form(own, leaving)
    own_person = await add_member(own, "VIEWER")
    own_team = await team_with(own, own_person, name="Own team")
    await grant(own, own_form.form_id, own_person.id, "VIEWER")
    await grant(own, own_form.form_id, own_team.id, "VIEWER", subject_type="group")

    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=leaving.id, roles=["COLLABORATOR"]
        )
    )
    bystander = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, leaving, bystander, name="Shared")
    await grant(workspace, workspace_form.form_id, leaving.id, "EDITOR")
    await grant(workspace, workspace_form.form_id, bystander.id, "VIEWER")

    await container.workspace_service().delete_workspaces_of_user_with_forms(leaving)

    remaining = {(g.subject_type, g.subject_id) for g in await grants_of(workspace, workspace_form)}
    assert remaining == {("user", bystander.id)}
    assert await container.member_group_repo().member_ids(workspace.id, team.id) == [
        bystander.id
    ]
    # the workspace that went with the account: nothing of it is left
    assert await container.workspace_repo().find_by_id(own.id) is None
    assert await container.form_access_grant_repo().list_for_form(own.id, own_form.form_id) == []
    assert await container.member_group_repo().list_in_workspace(own.id) == []
    assert await container.member_group_repo().member_ids(own.id, own_team.id) == []
    # one entry in the workspace that stays: ids and a count only
    (event,) = await audit_events(workspace, ACCESS_MEMBER_PURGED)
    assert (event.target_user_id, event.count) == (leaving.id, 2)
    assert not await audit_events(own)


async def test_the_clean_up_leaves_other_workspaces_and_people_alone(
    workspace, workspace_1, workspace_form, no_storage, either_switch
):
    person = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, person.id, "VIEWER")
    elsewhere = await add_member(workspace_1, "VIEWER")
    form_1 = await create_form(workspace_1, testUser1)
    await grant(workspace_1, form_1.form_id, elsewhere.id, "VIEWER")
    team_1 = await team_with(workspace_1, elsewhere, name="Elsewhere")

    cleanup = container.form_access_cleanup()
    await cleanup.forget_account(person.id)
    await cleanup.forget_workspaces([str(RecordId())])

    assert await grants_of(workspace, workspace_form) == []
    assert len(await grants_of(workspace_1, form_1)) == 1
    assert await container.member_group_repo().member_ids(workspace_1.id, team_1.id) == [
        elsewhere.id
    ]
