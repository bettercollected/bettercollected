"""Member roles (docs/enterprise-access-model.md, step b): the members list
shows each member's role, admins change roles and invite with one, and the
owner transfers ownership to an Admin."""

from unittest.mock import patch

import pytest
from beanie import PydanticObjectId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.authorization_service import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    EDITOR_PERMISSIONS,
    VIEWER_PERMISSIONS,
)
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser, testUser1

admin = User(id=str(PydanticObjectId()), sub="roles-admin@example.com")
viewer = User(id=str(PydanticObjectId()), sub="roles-viewer@example.com")


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _members_url(workspace_id) -> str:
    return f"/api/v1/workspaces/{workspace_id}/members"


async def _add(workspace_id, user: User, roles, disabled=False):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace_id, user_id=user.id, roles=roles, disabled=disabled
        )
    )


async def _stored_roles(workspace_id, user: User):
    membership = await container.workspace_user_repo().find_workspace_user(
        PydanticObjectId(workspace_id), PydanticObjectId(user.id)
    )
    return membership.roles


@pytest.fixture()
async def members(workspace):
    await _add(workspace.id, admin, [WorkspaceRoles.ADMIN])
    await _add(workspace.id, viewer, [WorkspaceRoles.VIEWER])
    return workspace


def _auth_users(*args, **kwargs):
    """The auth service's user lookup (and its invitation mail)."""
    ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
    return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in ids]}


@pytest.fixture()
def auth_service():
    async def get(*args, **kwargs):
        return _auth_users(*args, **kwargs)

    with patch("common.services.http_client.HttpClient.get", side_effect=get) as mock:
        yield mock


async def test_the_members_list_shows_each_role(
    client: AsyncClient, members, auth_service
):
    response = await client.get(_members_url(members.id), cookies=_cookies(testUser))

    assert response.status_code == 200, response.text
    roles = {m["id"]: (m["role"], m["roles"]) for m in response.json()}
    assert roles[testUser.id][0] == "OWNER"
    assert roles[admin.id] == ("ADMIN", ["ADMIN"])
    assert roles[viewer.id] == ("VIEWER", ["VIEWER"])
    # stored as COLLABORATOR, reported as EDITOR
    assert roles[invited_user.id] == ("EDITOR", ["EDITOR"])


async def test_a_deleted_account_never_lends_its_row_to_someone_else(
    client: AsyncClient, members
):
    """The auth service leaves out accounts it no longer has; every other
    member keeps their own name and email, and the missing one is listed by
    id only, marked as deleted."""

    async def users(*args, **kwargs):
        ids = [str(i) for i in kwargs["params"]["user_ids"]]
        return {
            "users_info": [
                {"_id": i, "email": f"{i}@example.com"}
                for i in ids
                if i != admin.id  # this account was deleted
            ]
        }

    with patch("common.services.http_client.HttpClient.get", side_effect=users):
        response = await client.get(
            _members_url(members.id), cookies=_cookies(testUser)
        )

    assert response.status_code == 200, response.text
    listed = {m["id"]: m for m in response.json()}
    assert listed[admin.id]["accountDeleted"] is True
    assert listed[admin.id]["email"] is None
    assert listed[admin.id]["role"] == "ADMIN"
    for member in (testUser, viewer, invited_user):
        assert listed[member.id]["email"] == f"{member.id}@example.com"
        assert not listed[member.id]["accountDeleted"]


@pytest.mark.parametrize(
    "role, stored",
    [
        ("VIEWER", WorkspaceRoles.VIEWER),
        ("REVIEWER", WorkspaceRoles.REVIEWER),
        ("PRIVACY_OFFICER", WorkspaceRoles.PRIVACY_OFFICER),
        ("ADMIN", WorkspaceRoles.ADMIN),
        # an Editor keeps the stored spelling every existing editor has
        ("EDITOR", WorkspaceRoles.COLLABORATOR),
        ("COLLABORATOR", WorkspaceRoles.COLLABORATOR),
    ],
)
async def test_an_admin_changes_a_members_role(
    client: AsyncClient, members, role, stored
):
    response = await client.patch(
        f"{_members_url(members.id)}/{invited_user.id}",
        json={"role": role},
        cookies=_cookies(admin),
    )

    assert response.status_code == 200, response.text
    expected = "EDITOR" if role == "COLLABORATOR" else role
    assert response.json()["role"] == expected
    assert await _stored_roles(members.id, invited_user) == [stored]


async def test_a_new_role_takes_effect_at_once(client: AsyncClient, members):
    await client.patch(
        f"{_members_url(members.id)}/{invited_user.id}",
        json={"role": "VIEWER"},
        cookies=_cookies(testUser),
    )

    authorization = container.authorization_service()
    assert (
        await authorization.effective_permissions(invited_user, members.id)
        == VIEWER_PERMISSIONS
    )
    refused = await client.post(
        f"/api/v1/workspaces/{members.id}/forms",
        data={"form_body": "{}"},
        cookies=_cookies(invited_user),
    )
    assert refused.status_code == 403


async def test_no_one_changes_the_owners_role(client: AsyncClient, members):
    response = await client.patch(
        f"{_members_url(members.id)}/{testUser.id}",
        json={"role": "VIEWER"},
        cookies=_cookies(admin),
    )

    assert response.status_code == 403
    assert "owner" in response.text.lower()
    assert await _stored_roles(members.id, testUser) == [WorkspaceRoles.ADMIN]


async def test_no_one_changes_their_own_role(client: AsyncClient, members):
    response = await client.patch(
        f"{_members_url(members.id)}/{admin.id}",
        json={"role": "VIEWER"},
        cookies=_cookies(admin),
    )

    assert response.status_code == 403
    assert await _stored_roles(members.id, admin) == [WorkspaceRoles.ADMIN]


async def test_owner_is_not_a_role_anyone_can_give(client: AsyncClient, members):
    """An Admin can't promote anyone above Admin: ownership is transferred."""
    response = await client.patch(
        f"{_members_url(members.id)}/{invited_user.id}",
        json={"role": "OWNER"},
        cookies=_cookies(admin),
    )

    assert response.status_code == 422
    assert await _stored_roles(members.id, invited_user) == [
        WorkspaceRoles.COLLABORATOR
    ]


@pytest.mark.parametrize("actor", [viewer, invited_user])
async def test_changing_roles_needs_members_manage(
    client: AsyncClient, members, actor
):
    target = admin if actor is viewer else viewer
    response = await client.patch(
        f"{_members_url(members.id)}/{target.id}",
        json={"role": "EDITOR"},
        cookies=_cookies(actor),
    )

    assert response.status_code == 403


async def test_changing_the_role_of_a_non_member_is_not_found(
    client: AsyncClient, members
):
    response = await client.patch(
        f"{_members_url(members.id)}/{testUser1.id}",
        json={"role": "VIEWER"},
        cookies=_cookies(admin),
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "role, stored, listed",
    [
        ("REVIEWER", "REVIEWER", "REVIEWER"),
        ("PRIVACY_OFFICER", "PRIVACY_OFFICER", "PRIVACY_OFFICER"),
        ("EDITOR", "COLLABORATOR", "EDITOR"),
        ("COLLABORATOR", "COLLABORATOR", "EDITOR"),
    ],
)
async def test_an_invitation_carries_its_role_into_the_membership(
    client: AsyncClient, members, auth_service, role, stored, listed
):
    newcomer = User(id=str(PydanticObjectId()), sub="newcomer@example.com")
    created = await client.post(
        f"{_members_url(members.id)}/invitations",
        json={"email": newcomer.sub, "role": role},
        cookies=_cookies(admin),
    )
    assert created.status_code == 200, created.text
    # reported as the API names it, whatever the stored spelling
    assert created.json()["role"] == listed
    mail = auth_service.call_args_list[-1].kwargs["params"]
    assert mail["role"] in {"Reviewer", "Privacy officer", "Editor"}

    listed_invitations = await client.get(
        f"{_members_url(members.id)}/invitations", cookies=_cookies(admin)
    )
    (invitation,) = [
        i for i in listed_invitations.json()["items"] if i["email"] == newcomer.sub
    ]
    assert invitation["role"] == listed

    accepted = await client.post(
        f"{_members_url(members.id)}/invitations/{invitation['invitationToken']}",
        params={"response_status": "ACCEPTED"},
        cookies=_cookies(newcomer),
    )
    assert accepted.status_code == 200, accepted.text
    assert await _stored_roles(members.id, newcomer) == [stored]


async def test_inviting_an_existing_member_is_refused(
    client: AsyncClient, members
):
    async def users(*args, **kwargs):
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in ids]}

    with patch("common.services.http_client.HttpClient.get", side_effect=users):
        response = await client.post(
            f"{_members_url(members.id)}/invitations",
            json={"email": f"{viewer.id}@example.com", "role": "EDITOR"},
            cookies=_cookies(admin),
        )

    assert response.status_code == 409
    assert "already a member" in response.text
    assert await _stored_roles(members.id, viewer) == [WorkspaceRoles.VIEWER]


@pytest.mark.parametrize("inviter_now", ["removed", "editor"])
async def test_accepting_rechecks_the_inviter(
    client: AsyncClient, members, auth_service, inviter_now
):
    """An Admin's invitation stops working once they no longer manage
    members (or no longer hold the role they gave)."""
    newcomer = User(id=str(PydanticObjectId()), sub="late@example.com")
    created = await client.post(
        f"{_members_url(members.id)}/invitations",
        json={"email": newcomer.sub, "role": "ADMIN"},
        cookies=_cookies(admin),
    )
    assert created.status_code == 200, created.text
    token = created.json()["invitation_token"]

    repo = container.workspace_user_repo()
    if inviter_now == "removed":
        await repo.delete(members.id, admin.id)
    else:
        membership = await repo.find_workspace_user(
            members.id, PydanticObjectId(admin.id)
        )
        membership.roles = [WorkspaceRoles.COLLABORATOR]
        await repo.save(membership)

    accepted = await client.post(
        f"{_members_url(members.id)}/invitations/{token}",
        params={"response_status": "ACCEPTED"},
        cookies=_cookies(newcomer),
    )

    assert accepted.status_code == 403
    assert "invite you again" in accepted.text
    assert await repo.find_workspace_user(
        members.id, PydanticObjectId(newcomer.id)
    ) is None


async def test_an_invitation_with_an_unknown_role_loads_and_grants_nothing(
    client: AsyncClient, members
):
    """A role from a newer release still loads (rollback safety)."""
    invitation = await container.workspace_invitation_repo().create_workspace_invitation(
        members.id,
        InvitationRequest(email="future@example.com", role=WorkspaceRoles.VIEWER),
    )
    invitation.role = "SOMETHING_NEW"
    await container.workspace_invitation_repo().save(invitation)

    stored = await container.workspace_invitation_repo().get_workspace_invitation_by_token(
        workspace_id=members.id, invitation_token=invitation.invitation_token
    )
    assert stored.role == "SOMETHING_NEW"
    future = User(id=str(PydanticObjectId()), sub="future@example.com")
    accepted = await client.post(
        f"{_members_url(members.id)}/invitations/{invitation.invitation_token}",
        params={"response_status": "ACCEPTED"},
        cookies=_cookies(future),
    )
    assert accepted.status_code == 200, accepted.text
    assert not await container.authorization_service().effective_permissions(
        future, members.id
    )


async def test_inviting_again_changes_the_role(client: AsyncClient, members):
    repo = container.workspace_invitation_repo()
    await repo.create_workspace_invitation(
        members.id,
        InvitationRequest(email="again@example.com", role=WorkspaceRoles.VIEWER),
    )
    again = await repo.create_workspace_invitation(
        members.id,
        InvitationRequest(email="again@example.com", role=WorkspaceRoles.REVIEWER),
    )

    assert again.role == WorkspaceRoles.REVIEWER


# --- owner transfer


@pytest.fixture()
async def team_workspace():
    """A workspace that is neither the owner's personal one nor on a paid
    plan: the only kind ownership can move away from."""
    workspace = await container.workspace_repo().save(
        WorkspaceDocument(
            title="Team",
            description="",
            owner_id=testUser.id,
            workspace_name="team-roles",
            default=False,
            is_pro=False,
        )
    )
    await _add(workspace.id, testUser, [WorkspaceRoles.ADMIN])
    await _add(workspace.id, admin, [WorkspaceRoles.ADMIN])
    await _add(workspace.id, viewer, [WorkspaceRoles.VIEWER])
    return workspace


def _transfer_url(workspace_id, user: User) -> str:
    return f"{_members_url(workspace_id)}/{user.id}/transfer-ownership"


async def test_the_owner_transfers_to_an_admin_and_becomes_an_admin(
    client: AsyncClient, team_workspace
):
    response = await client.post(
        _transfer_url(team_workspace.id, admin), cookies=_cookies(testUser)
    )

    assert response.status_code == 200, response.text
    workspace = await container.workspace_repo().find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == admin.id
    authorization = container.authorization_service()
    assert (
        await authorization.effective_permissions(admin, workspace.id)
        == ALL_PERMISSIONS
    )
    assert (
        await authorization.effective_permissions(testUser, workspace.id)
        == ADMIN_PERMISSIONS
    )
    assert await _stored_roles(workspace.id, testUser) == [WorkspaceRoles.ADMIN]
    # and the old owner's role can now be changed by the new owner
    demoted = await client.patch(
        f"{_members_url(workspace.id)}/{testUser.id}",
        json={"role": "EDITOR"},
        cookies=_cookies(admin),
    )
    assert demoted.status_code == 200, demoted.text
    assert (
        await authorization.effective_permissions(testUser, workspace.id)
        == EDITOR_PERMISSIONS
    )


async def test_a_transfer_is_conditional_on_the_current_owner(team_workspace):
    repo = container.workspace_repo()
    # someone else is no longer the owner: nothing changes
    assert await repo.set_owner_if(team_workspace.id, viewer.id, admin.id) is None
    workspace = await repo.find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == testUser.id

    moved = await repo.set_owner_if(team_workspace.id, testUser.id, admin.id)
    assert str(moved.owner_id) == admin.id
    # a second transfer from the same (now former) owner can't land
    assert await repo.set_owner_if(team_workspace.id, testUser.id, viewer.id) is None
    workspace = await repo.find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == admin.id


async def test_a_transfer_is_undone_when_the_target_stops_being_an_admin(
    client: AsyncClient, team_workspace, monkeypatch
):
    """The target is demoted between the check and the owner change: the
    change is undone and the caller stays the owner."""
    service = container.workspace_members_service()
    users = service.workspace_user_service
    real_find = users.find_workspace_user
    calls = {"target": 0}

    async def find(workspace_id, user_id):
        membership = await real_find(workspace_id, user_id)
        if str(user_id) == admin.id:
            calls["target"] += 1
            if calls["target"] > 1 and membership is not None:
                membership.roles = [WorkspaceRoles.VIEWER]  # demoted meanwhile
        return membership

    monkeypatch.setattr(users, "find_workspace_user", find)
    response = await client.post(
        _transfer_url(team_workspace.id, admin), cookies=_cookies(testUser)
    )

    assert response.status_code == 409
    workspace = await container.workspace_repo().find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == testUser.id


async def test_only_the_owner_transfers(client: AsyncClient, team_workspace):
    response = await client.post(
        _transfer_url(team_workspace.id, viewer), cookies=_cookies(admin)
    )

    assert response.status_code == 403
    workspace = await container.workspace_repo().find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == testUser.id


@pytest.mark.parametrize("disabled", [False, True])
async def test_ownership_goes_only_to_an_active_admin(
    client: AsyncClient, team_workspace, disabled
):
    if disabled:
        target = User(id=str(PydanticObjectId()), sub="disabled-admin@example.com")
        await _add(team_workspace.id, target, [WorkspaceRoles.ADMIN], disabled=True)
    else:
        target = viewer
    response = await client.post(
        _transfer_url(team_workspace.id, target), cookies=_cookies(testUser)
    )

    assert response.status_code == 400
    assert "Admin" in response.text
    workspace = await container.workspace_repo().find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == testUser.id


async def test_ownership_never_goes_to_a_non_member(
    client: AsyncClient, team_workspace
):
    response = await client.post(
        _transfer_url(team_workspace.id, testUser1), cookies=_cookies(testUser)
    )

    assert response.status_code == 400


async def test_a_paid_workspace_is_not_transferred(
    client: AsyncClient, team_workspace
):
    """The plan is billed to the owner's account, not to the workspace."""
    await container.workspace_repo().set_fields(team_workspace, {"is_pro": True})

    response = await client.post(
        _transfer_url(team_workspace.id, admin), cookies=_cookies(testUser)
    )

    assert response.status_code == 409
    assert "paid plan" in response.text
    workspace = await container.workspace_repo().find_by_id(team_workspace.id)
    assert str(workspace.owner_id) == testUser.id


async def test_a_personal_workspace_is_not_transferred(
    client: AsyncClient, members
):
    response = await client.post(
        _transfer_url(members.id, admin), cookies=_cookies(testUser)
    )

    assert response.status_code == 409
    assert "personal" in response.text
    workspace = await container.workspace_repo().find_by_id(members.id)
    assert str(workspace.owner_id) == testUser.id


async def test_the_new_owner_holds_billing_only_after_the_transfer(
    client: AsyncClient, team_workspace
):
    authorization = container.authorization_service()
    assert not await authorization.has_permission(
        admin, Permission.WORKSPACE_BILLING, team_workspace.id
    )
    await client.post(
        _transfer_url(team_workspace.id, admin), cookies=_cookies(testUser)
    )
    assert await authorization.has_permission(
        admin, Permission.WORKSPACE_BILLING, team_workspace.id
    )
    assert not await authorization.has_permission(
        testUser, Permission.WORKSPACE_BILLING, team_workspace.id
    )
