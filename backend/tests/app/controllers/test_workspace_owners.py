"""Several owners (docs/enterprise-access-model.md, "Owners"): every owner
holds every permission, billing and the SSO configuration included. The
billing owner (``owner_id``) is the account the plan is billed to; other
owners are members with role OWNER. Only owners make, demote or remove
owners, the billing owner is never demoted or removed, a workspace always
keeps an active owner, and neither the directory nor SSO ever grants or
changes Owner."""

from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.scim import ScimUserState
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.authorization_service import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    DISABLED_WORKSPACE_OWNER_PERMISSIONS,
)
from backend.app.services.session_service import utcnow
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser
from tests.app.scim_helpers import (  # noqa: F401 — fixtures
    create_directory,
    deliver,
    event,
    group_data,
    member_of,
    members_list,
    scim_on,
    user_data,
)
from tests.app.sso_helpers import (
    DOMAIN,
    add_connection,
    sso_on,
    verify_domain,
)  # noqa: F401

co_owner = User(id=str(PydanticObjectId()), sub="co-owner@" + DOMAIN)
admin = User(id=str(PydanticObjectId()), sub="admin@" + DOMAIN)
viewer = User(id=str(PydanticObjectId()), sub="viewer@" + DOMAIN)


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _members(workspace_id) -> str:
    return f"/api/v1/workspaces/{workspace_id}/members"


async def _add(workspace_id, user: User, roles, disabled=False, **fields):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace_id,
            user_id=user.id,
            roles=roles,
            disabled=disabled,
            **fields,
        )
    )


async def _membership(workspace_id, user: User):
    return await container.workspace_user_repo().find_workspace_user(
        PydanticObjectId(workspace_id), PydanticObjectId(user.id)
    )


async def _permissions(user: User, workspace_id):
    return await container.authorization_service().effective_permissions(
        user, workspace_id
    )


def _users(*args, **kwargs):
    ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
    return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in ids]}


@pytest.fixture()
def auth_service():
    async def get(*args, **kwargs):
        return _users(*args, **kwargs)

    with patch("common.services.http_client.HttpClient.get", side_effect=get) as mock:
        yield mock


@pytest.fixture()
async def owners(workspace):
    """testUser is the billing owner, co_owner a second owner."""
    await _add(workspace.id, co_owner, [WorkspaceRoles.OWNER])
    await _add(workspace.id, admin, [WorkspaceRoles.ADMIN])
    await _add(workspace.id, viewer, [WorkspaceRoles.VIEWER])
    return workspace


# -- who is an owner ----------------------------------------------------------


async def test_every_owner_holds_every_permission(owners):
    assert await _permissions(testUser, owners.id) == ALL_PERMISSIONS
    assert await _permissions(co_owner, owners.id) == ALL_PERMISSIONS
    assert await _permissions(admin, owners.id) == ADMIN_PERMISSIONS
    authorization = container.authorization_service()
    assert await authorization.is_owner(co_owner, owners.id)
    assert not await authorization.is_owner(admin, owners.id)


async def test_a_disabled_owner_membership_grants_nothing(workspace):
    await _add(workspace.id, co_owner, [WorkspaceRoles.OWNER], disabled=True)
    assert not await _permissions(co_owner, workspace.id)


async def test_the_members_list_shows_owners_and_the_billing_owner(
    client: AsyncClient, owners, auth_service
):
    response = await client.get(_members(owners.id), cookies=_cookies(co_owner))

    assert response.status_code == 200, response.text
    listed = {m["id"]: m for m in response.json()}
    assert listed[testUser.id]["role"] == "OWNER"
    assert listed[testUser.id]["billingOwner"] is True
    assert listed[co_owner.id]["role"] == "OWNER"
    assert listed[co_owner.id]["roles"] == ["OWNER"]
    assert listed[co_owner.id]["billingOwner"] is False
    assert listed[admin.id]["role"] == "ADMIN"


async def test_my_workspaces_say_which_ones_i_own(client: AsyncClient, owners):
    for user, expected in ((co_owner, True), (testUser, True), (admin, False)):
        response = await client.get("/api/v1/workspaces/mine", cookies=_cookies(user))
        assert response.status_code == 200, response.text
        (listed,) = [w for w in response.json() if w["id"] == str(owners.id)]
        assert listed["isOwner"] is expected, user.sub
        assert listed["ownerId"] == testUser.id


# -- making owners ------------------------------------------------------------


@pytest.mark.parametrize("actor", [testUser, co_owner], ids=["billing", "co_owner"])
async def test_an_owner_makes_a_member_an_owner(client: AsyncClient, owners, actor):
    response = await client.patch(
        f"{_members(owners.id)}/{admin.id}",
        json={"role": "OWNER"},
        cookies=_cookies(actor),
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "OWNER"
    assert (await _membership(owners.id, admin)).roles == [WorkspaceRoles.OWNER]
    assert await _permissions(admin, owners.id) == ALL_PERMISSIONS


async def test_an_admin_never_makes_an_owner(client: AsyncClient, owners, auth_service):
    promoted = await client.patch(
        f"{_members(owners.id)}/{viewer.id}",
        json={"role": "OWNER"},
        cookies=_cookies(admin),
    )
    invited = await client.post(
        f"{_members(owners.id)}/invitations",
        json={"email": "newcomer@example.com", "role": "OWNER"},
        cookies=_cookies(admin),
    )

    assert promoted.status_code == 403 and "Only an owner" in promoted.text
    assert invited.status_code == 403 and "Only an owner" in invited.text
    assert (await _membership(owners.id, viewer)).roles == [WorkspaceRoles.VIEWER]
    invitations = await client.get(
        f"{_members(owners.id)}/invitations", cookies=_cookies(admin)
    )
    assert all(
        i["email"] != "newcomer@example.com" for i in invitations.json()["items"]
    )


async def test_an_owner_invites_an_owner(client: AsyncClient, owners, auth_service):
    newcomer = User(id=str(PydanticObjectId()), sub="new-owner@example.com")
    created = await client.post(
        f"{_members(owners.id)}/invitations",
        json={"email": newcomer.sub, "role": "OWNER"},
        cookies=_cookies(co_owner),
    )
    assert created.status_code == 200, created.text
    assert created.json()["role"] == "OWNER"
    assert auth_service.call_args_list[-1].kwargs["params"]["role"] == "Owner"

    accepted = await client.post(
        f"{_members(owners.id)}/invitations/{created.json()['invitation_token']}",
        params={"response_status": "ACCEPTED"},
        cookies=_cookies(newcomer),
    )

    assert accepted.status_code == 200, accepted.text
    assert await _permissions(newcomer, owners.id) == ALL_PERMISSIONS


async def test_an_owner_invitation_lapses_with_its_senders_ownership(
    client: AsyncClient, owners, auth_service
):
    newcomer = User(id=str(PydanticObjectId()), sub="late-owner@example.com")
    created = await client.post(
        f"{_members(owners.id)}/invitations",
        json={"email": newcomer.sub, "role": "OWNER"},
        cookies=_cookies(co_owner),
    )
    assert created.status_code == 200, created.text
    demoted = await client.patch(
        f"{_members(owners.id)}/{co_owner.id}",
        json={"role": "ADMIN"},
        cookies=_cookies(testUser),
    )
    assert demoted.status_code == 200, demoted.text

    accepted = await client.post(
        f"{_members(owners.id)}/invitations/{created.json()['invitation_token']}",
        params={"response_status": "ACCEPTED"},
        cookies=_cookies(newcomer),
    )

    assert accepted.status_code == 403
    assert await _membership(owners.id, newcomer) is None


# -- demoting and removing owners ---------------------------------------------


async def test_an_admin_neither_demotes_nor_removes_an_owner(
    client: AsyncClient, owners, auth_service
):
    demoted = await client.patch(
        f"{_members(owners.id)}/{co_owner.id}",
        json={"role": "VIEWER"},
        cookies=_cookies(admin),
    )
    removed = await client.delete(
        f"{_members(owners.id)}/{co_owner.id}", cookies=_cookies(admin)
    )

    assert demoted.status_code == 403 and "Only an owner" in demoted.text
    assert removed.status_code == 403 and "Only an owner" in removed.text
    assert (await _membership(owners.id, co_owner)).roles == [WorkspaceRoles.OWNER]


async def test_an_owner_demotes_and_removes_another_owner(
    client: AsyncClient, owners, auth_service
):
    demoted = await client.patch(
        f"{_members(owners.id)}/{co_owner.id}",
        json={"role": "ADMIN"},
        cookies=_cookies(testUser),
    )
    assert demoted.status_code == 200, demoted.text
    assert await _permissions(co_owner, owners.id) == ADMIN_PERMISSIONS

    promoted = await client.patch(
        f"{_members(owners.id)}/{co_owner.id}",
        json={"role": "OWNER"},
        cookies=_cookies(testUser),
    )
    assert promoted.status_code == 200, promoted.text
    removed = await client.delete(
        f"{_members(owners.id)}/{co_owner.id}", cookies=_cookies(testUser)
    )
    assert removed.status_code == 200, removed.text
    assert await _membership(owners.id, co_owner) is None


@pytest.mark.parametrize("actor", ["co_owner", "admin"])
async def test_the_billing_owner_is_neither_demoted_nor_removed(
    client: AsyncClient, owners, auth_service, actor
):
    user = co_owner if actor == "co_owner" else admin
    demoted = await client.patch(
        f"{_members(owners.id)}/{testUser.id}",
        json={"role": "ADMIN"},
        cookies=_cookies(user),
    )
    removed = await client.delete(
        f"{_members(owners.id)}/{testUser.id}", cookies=_cookies(user)
    )

    assert demoted.status_code == 403 and "billing owner" in demoted.text
    assert removed.status_code == 403 and "billing owner" in removed.text
    assert await _permissions(testUser, owners.id) == ALL_PERMISSIONS


async def test_an_owner_may_leave_while_another_owner_stays(
    client: AsyncClient, owners, auth_service
):
    left = await client.delete(
        f"{_members(owners.id)}/{co_owner.id}", cookies=_cookies(co_owner)
    )

    assert left.status_code == 200, left.text
    assert await _membership(owners.id, co_owner) is None


async def test_the_last_active_owner_cannot_leave(
    client: AsyncClient, owners, auth_service
):
    """The billing owner's membership is disabled (data from before several
    owners, or set by hand): the co-owner is the only active owner and
    can't remove themselves."""
    billing = await _membership(owners.id, testUser)
    billing.disabled = True
    await container.workspace_user_repo().save(billing)

    left = await client.delete(
        f"{_members(owners.id)}/{co_owner.id}", cookies=_cookies(co_owner)
    )

    assert left.status_code == 409
    assert "at least one active owner" in left.text
    assert (await _membership(owners.id, co_owner)).roles == [WorkspaceRoles.OWNER]


# -- single sign-on -----------------------------------------------------------


@pytest.fixture()
async def sso_workspace(client, owners, sso_on):
    await verify_domain(owners.id)
    connection = await add_connection(owners.id)
    return owners, connection


def _sso(workspace, suffix="") -> str:
    return f"/api/v1/workspaces/{workspace.id}/sso{suffix}"


async def test_a_co_owner_changes_the_sso_configuration(
    client: AsyncClient, sso_workspace
):
    workspace, connection = sso_workspace
    overview = await client.get(_sso(workspace), cookies=_cookies(co_owner))
    assert overview.status_code == 200 and overview.json()["canManage"] is True

    changed = await client.put(
        _sso(workspace, "/settings"),
        json={"defaultRole": "REVIEWER", "ssoRequired": True},
        cookies=_cookies(co_owner),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["defaultRole"] == "REVIEWER"
    assert changed.json()["ssoRequired"] is True
    disabled = await client.put(
        _sso(workspace, "/settings"),
        json={"ssoRequired": False},
        cookies=_cookies(co_owner),
    )
    assert disabled.status_code == 200, disabled.text
    off = await client.post(
        _sso(workspace, f"/connections/{connection.id}/disable"),
        cookies=_cookies(co_owner),
    )
    assert off.status_code == 200, off.text

    refused = await client.put(
        _sso(workspace, "/settings"),
        json={"defaultRole": "VIEWER"},
        cookies=_cookies(admin),
    )
    assert refused.status_code == 403
    assert (await client.get(_sso(workspace), cookies=_cookies(admin))).json()[
        "canManage"
    ] is False


async def test_owner_is_never_the_sso_default_role(client: AsyncClient, sso_workspace):
    workspace, _ = sso_workspace
    for user in (testUser, co_owner):
        reply = await client.put(
            _sso(workspace, "/settings"),
            json={"defaultRole": "OWNER"},
            cookies=_cookies(user),
        )
        assert reply.status_code == 422 and reply.json()["code"] == "invalid_role"


async def _session(user_id: str, method: str = "otp") -> SessionDocument:
    now = utcnow()
    return await container.session_repo().save(
        SessionDocument(
            id=PydanticObjectId(),
            user_id=user_id,
            refresh_jti="j",
            method=method,
            expires_at=now.replace(year=now.year + 1),
        )
    )


async def test_every_owner_keeps_the_break_glass(
    client: AsyncClient, sso_workspace, sso_on
):
    """While SSO is required, each owner (not only the billing owner) may
    still sign in with an email code, and their sessions are kept when the
    requirement is switched on."""
    workspace, _ = sso_workspace
    _, auth = sso_on
    auth.add_account(co_owner.sub, user_id=co_owner.id)
    auth.add_account(admin.sub, user_id=admin.id)
    for user in (co_owner, admin):
        await _session(user.id)
    reply = await client.put(
        _sso(workspace, "/settings"),
        json={"ssoRequired": True, "revokeSessions": True},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200, reply.text
    sessions = container.session_service()
    assert len(await sessions.list_for_user(co_owner.id)) == 1
    assert await sessions.list_for_user(admin.id) == []

    policy = container.sso_policy_service()
    assert await policy.code_sign_in_scope(co_owner.sub, user_id=co_owner.id) is None
    # before the account is known: by the owners' emails
    assert await policy.code_sign_in_scope(co_owner.sub) is None
    otp_session = await _session(co_owner.id)
    assert not await policy.session_must_end(co_owner.sub, otp_session, co_owner.id)
    for kwargs in ({"user_id": admin.id}, {}):
        with pytest.raises(Exception) as refused:
            await policy.code_sign_in_scope(admin.sub, **kwargs)
        assert "sso_required" in str(refused.value.content)
    # a co-owner whose membership is disabled has no break-glass
    membership = await _membership(workspace.id, co_owner)
    membership.disabled = True
    await container.workspace_user_repo().save(membership)
    with pytest.raises(Exception):
        await policy.code_sign_in_scope(co_owner.sub, user_id=co_owner.id)


# -- the directory (SCIM) -----------------------------------------------------

JANE = "jane@" + DOMAIN


@pytest.fixture()
async def directory(client, owners, scim_on, members_list):
    document, _ = await create_directory(client, owners, _cookies(testUser))
    return document


async def test_the_directory_never_changes_an_owner(
    client: AsyncClient, owners, directory, scim_on
):
    """A member the directory provisioned can be made an owner by hand;
    from then on the directory changes neither their role nor their status,
    and never grants Owner itself."""
    polis, auth = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    jane = auth.accounts[JANE]["id"]
    assert (await member_of(owners.id, jane)).roles == [WorkspaceRoles.VIEWER]

    promoted = await client.patch(
        f"{_members(owners.id)}/{jane}",
        json={"role": "OWNER"},
        cookies=_cookies(co_owner),
    )
    assert promoted.status_code == 200, promoted.text

    # a group mapped to Admin does not touch the owner's role
    await deliver(
        client,
        directory,
        polis,
        event(directory, "group.created", group_data("g", "IT")),
    )
    group = await container.scim_group_repo().find(directory.id, "g")
    mapped = await client.put(
        f"/api/v1/workspaces/{owners.id}/scim/groups/{group.id}",
        json={"role": "ADMIN"},
        cookies=_cookies(co_owner),
    )
    assert mapped.status_code == 200, mapped.text
    await deliver(
        client,
        directory,
        polis,
        event(
            directory,
            "group.user_added",
            {**user_data("u1", JANE), "group": group_data("g", "IT")},
        ),
    )
    assert (await member_of(owners.id, jane)).roles == [WorkspaceRoles.OWNER]

    # deactivation at the IdP leaves the owner alone
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u1", JANE, active=False)),
    )
    member = await member_of(owners.id, jane)
    assert not member.disabled and member.roles == [WorkspaceRoles.OWNER]
    record = await container.scim_user_repo().find(directory.id, "u1")
    assert (record.state, record.reason) == (ScimUserState.IGNORED, "owner_protected")

    listed = await client.get(_members(owners.id), cookies=_cookies(testUser))
    (row,) = [m for m in listed.json() if m["id"] == jane]
    assert row["managedByDirectory"] is False


async def test_a_directory_group_never_maps_to_owner(
    client: AsyncClient, owners, directory, scim_on
):
    polis, _ = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "group.created", group_data("g", "IT")),
    )
    group = await container.scim_group_repo().find(directory.id, "g")
    reply = await client.put(
        f"/api/v1/workspaces/{owners.id}/scim/groups/{group.id}",
        json={"role": "OWNER"},
        cookies=_cookies(co_owner),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "invalid_role"


# -- billing ------------------------------------------------------------------


@pytest.fixture()
async def paid_team():
    """A paid team workspace billed to testUser, with a co-owner, an Admin
    and an Editor."""
    workspace = await container.workspace_repo().save(
        WorkspaceDocument(
            title="Paid team",
            description="",
            owner_id=testUser.id,
            workspace_name="paid-team-owners",
            default=False,
            is_pro=True,
        )
    )
    await _add(workspace.id, testUser, [WorkspaceRoles.ADMIN])
    await _add(workspace.id, co_owner, [WorkspaceRoles.OWNER])
    await _add(workspace.id, admin, [WorkspaceRoles.ADMIN])
    await _add(workspace.id, invited_user, [WorkspaceRoles.COLLABORATOR])
    return workspace


async def test_a_downgrade_keeps_every_owner_and_disables_the_others(paid_team):
    service = container.workspace_service()
    await service.downgrade_user_workspace(testUser.id)

    workspace = await container.workspace_repo().find_by_id(paid_team.id)
    assert workspace.disabled and not workspace.is_pro
    assert not (await _membership(paid_team.id, co_owner)).disabled
    assert (await _membership(paid_team.id, admin)).disabled
    for owner in (testUser, co_owner):
        assert (
            await _permissions(owner, paid_team.id)
            == DISABLED_WORKSPACE_OWNER_PERMISSIONS
        )
    assert not await _permissions(admin, paid_team.id)

    await service.upgrade_user_workspace(testUser.id)
    assert not (await _membership(paid_team.id, admin)).disabled
    assert await _permissions(co_owner, paid_team.id) == ALL_PERMISSIONS


async def test_a_co_owners_own_plan_never_changes_the_workspace(paid_team):
    service = container.workspace_service()
    await service.downgrade_user_workspace(co_owner.id)

    workspace = await container.workspace_repo().find_by_id(paid_team.id)
    assert workspace.is_pro and not workspace.disabled
    assert not (await _membership(paid_team.id, admin)).disabled

    await container.workspace_repo().set_fields(workspace, {"is_pro": False})
    await service.upgrade_user_workspace(co_owner.id)
    workspace = await container.workspace_repo().find_by_id(paid_team.id)
    assert not workspace.is_pro


@pytest.mark.parametrize(
    "path, params",
    [
        ("/api/v1/stripe/session/create/portal", {}),
        ("/api/v1/stripe/session/create/checkout", {"price_id": "price_1"}),
    ],
)
async def test_billing_sessions_are_always_the_callers_own(
    client: AsyncClient, paid_team, path, params
):
    """Stripe customers are per person: a co-owner's billing link opens their
    own portal or checkout, never the billing owner's."""
    stripe_call = AsyncMock(return_value="https://billing.example.test/session")
    with patch("common.services.http_client.HttpClient.get", stripe_call):
        response = await client.get(path, params=params, cookies=_cookies(co_owner))

    assert response.status_code in (302, 307), response.text
    (call,) = [
        c for c in stripe_call.call_args_list if "/stripe/session" in str(c.args[0])
    ]
    assert call.kwargs["params"]["user_id"] == co_owner.id
    assert testUser.id not in str(call)
