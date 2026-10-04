"""The permission catalogue, the workspace roles and the authorization
service's rules (docs/enterprise-access-model.md, steps a and b)."""

import pytest
from beanie import PydanticObjectId
from common.models.user import User

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.authorization_service import (
    ALL_PERMISSIONS,
    EDITOR_PERMISSIONS,
    permissions_for,
)
from tests.app.controllers.data import invited_user, testUser, testUser1

P = Permission


def test_the_catalogue_is_the_documented_one():
    assert {p.value for p in Permission} == {
        "workspace.manage",
        "workspace.billing",
        "members.manage",
        "security.manage",
        "ai.manage",
        "audit.read",
        "form.create",
        "form.read",
        "form.edit",
        "form.delete",
        "form.share",
        "response.read",
        "response.annotate",
        "response.export",
        "response.delete",
        "privacy.manage",
        "analytics.read",
    }


def test_the_owner_holds_everything():
    assert permissions_for([], is_owner=True) == ALL_PERMISSIONS
    assert permissions_for([WorkspaceRoles.COLLABORATOR], is_owner=True) == (
        ALL_PERMISSIONS
    )


def test_an_admin_holds_everything_but_billing():
    assert permissions_for([WorkspaceRoles.ADMIN], is_owner=False) == (
        ALL_PERMISSIONS - {P.WORKSPACE_BILLING}
    )


# The doc's §2 table, written out independently of the service's constants.
ROLE_TABLE = {
    "EDITOR": {
        P.FORM_CREATE,
        P.FORM_READ,
        P.FORM_EDIT,
        P.FORM_DELETE,
        P.FORM_SHARE,
        P.RESPONSE_READ,
        P.RESPONSE_ANNOTATE,
        P.RESPONSE_EXPORT,
        P.RESPONSE_DELETE,
        P.ANALYTICS_READ,
    },
    "REVIEWER": {P.FORM_READ, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.ANALYTICS_READ},
    "VIEWER": {P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ},
    "PRIVACY_OFFICER": {P.FORM_READ, P.PRIVACY_MANAGE, P.ANALYTICS_READ, P.AUDIT_READ},
}


@pytest.mark.parametrize("role", sorted(ROLE_TABLE))
def test_each_role_grants_exactly_its_documented_set(role):
    assert permissions_for([role], is_owner=False) == ROLE_TABLE[role]
    assert permissions_for([WorkspaceRoles(role)], is_owner=False) == ROLE_TABLE[role]


def test_a_collaborator_is_an_editor_without_privacy_manage():
    """COLLABORATOR is read as EDITOR; since step b it no longer carries
    privacy.manage."""
    granted = permissions_for([WorkspaceRoles.COLLABORATOR], is_owner=False)
    assert granted == EDITOR_PERMISSIONS == ROLE_TABLE["EDITOR"]
    for workspace_level in (
        P.WORKSPACE_MANAGE,
        P.WORKSPACE_BILLING,
        P.MEMBERS_MANAGE,
        P.SECURITY_MANAGE,
        P.AI_MANAGE,
        P.AUDIT_READ,
        P.PRIVACY_MANAGE,
    ):
        assert workspace_level not in granted


def test_the_privacy_officer_never_reads_answers():
    granted = permissions_for([WorkspaceRoles.PRIVACY_OFFICER], is_owner=False)
    for answers in (P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.RESPONSE_EXPORT):
        assert answers not in granted


@pytest.mark.parametrize("roles", [[], None])
def test_a_legacy_membership_without_roles_is_an_editor(roles):
    """``roles: []`` is the schema default, from before roles existed; such
    memberships always had full content access."""
    assert permissions_for(roles, is_owner=False) == EDITOR_PERMISSIONS


@pytest.mark.parametrize("roles", [["FORM_CREATOR"], ["OWNER"], ["SOMETHING_NEW"]])
def test_an_unknown_role_grants_nothing(roles):
    assert permissions_for(roles, is_owner=False) == frozenset()


def test_roles_add_up_and_unknown_ones_add_nothing():
    assert permissions_for(["VIEWER", "FORM_CREATOR"], is_owner=False) == (
        ROLE_TABLE["VIEWER"]
    )
    assert permissions_for(["VIEWER", "PRIVACY_OFFICER"], is_owner=False) == (
        ROLE_TABLE["VIEWER"] | ROLE_TABLE["PRIVACY_OFFICER"]
    )


async def test_a_membership_with_an_unknown_role_loads_and_holds_nothing(workspace):
    """A role from a newer release (or legacy data) doesn't break loading."""
    member = User(id=str(PydanticObjectId()), sub="future@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=member.id, roles=["SOMETHING_NEW"]
        )
    )
    stored = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(member.id)
    )
    assert stored.roles == ["SOMETHING_NEW"]
    authorization = container.authorization_service()
    assert not await authorization.effective_permissions(member, workspace.id)


async def test_no_user_or_bad_ids_hold_nothing(workspace):
    authorization = container.authorization_service()
    assert not await authorization.effective_permissions(None, workspace.id)
    assert not await authorization.effective_permissions(testUser, "not-an-id")
    assert not await authorization.effective_permissions(testUser, None)
    stranger = User(id="not-an-id", sub="x@example.com")
    assert not await authorization.effective_permissions(stranger, workspace.id)


async def test_owner_admin_and_collaborator(workspace):
    authorization = container.authorization_service()
    admin = User(id=str(PydanticObjectId()), sub="admin@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=admin.id, roles=[WorkspaceRoles.ADMIN]
        )
    )

    assert await authorization.effective_permissions(testUser, workspace.id) == (
        ALL_PERMISSIONS
    )
    assert P.WORKSPACE_BILLING not in await authorization.effective_permissions(
        admin, str(workspace.id)
    )
    assert await authorization.has_permission(
        invited_user, P.RESPONSE_ANNOTATE, workspace.id
    )
    assert not await authorization.has_permission(
        invited_user, P.MEMBERS_MANAGE, workspace.id
    )
    assert not await authorization.has_permission(testUser1, P.FORM_READ, workspace.id)


async def test_a_disabled_membership_holds_nothing(workspace):
    """#770: an ADMIN role on a disabled membership grants nothing."""
    disabled = User(id=str(PydanticObjectId()), sub="disabled@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=disabled.id,
            roles=[WorkspaceRoles.ADMIN],
            disabled=True,
        )
    )
    authorization = container.authorization_service()

    assert not await authorization.effective_permissions(disabled, workspace.id)
    with pytest.raises(HTTPException) as refused:
        await authorization.authorize(disabled, P.MEMBERS_MANAGE, workspace.id)
    assert refused.value.status_code == 403


async def test_form_scope_is_checked_after_the_permission(
    workspace, workspace_1, workspace_form
):
    authorization = container.authorization_service()
    await authorization.authorize(
        testUser, P.FORM_EDIT, workspace.id, form_id=workspace_form.form_id
    )

    # a member naming a form of another workspace: 404
    with pytest.raises(HTTPException) as missing:
        await authorization.authorize(
            testUser1, P.FORM_EDIT, workspace_1.id, form_id=workspace_form.form_id
        )
    assert missing.value.status_code == 404
    assert not await authorization.has_permission(
        testUser1, P.FORM_EDIT, workspace_1.id, form_id=workspace_form.form_id
    )

    # a non-member learns nothing about the form: 403 first
    with pytest.raises(HTTPException) as refused:
        await authorization.authorize(
            testUser1, P.FORM_EDIT, workspace.id, form_id=str(PydanticObjectId())
        )
    assert refused.value.status_code == 403


async def test_a_disabled_workspace_is_read_and_privacy_for_its_owner(workspace):
    """A downgraded owner keeps reading forms and responses and answering
    deletion requests (GDPR); nothing else, and no one else."""
    workspace.disabled = True
    await container.workspace_repo().save(workspace)
    authorization = container.authorization_service()

    assert await authorization.effective_permissions(testUser, workspace.id) == {
        P.FORM_READ,
        P.RESPONSE_READ,
        P.RESPONSE_EXPORT,
        P.RESPONSE_DELETE,
        P.PRIVACY_MANAGE,
        P.ANALYTICS_READ,
    }
    assert not await authorization.effective_permissions(invited_user, workspace.id)
    with pytest.raises(HTTPException) as refused:
        await authorization.authorize(testUser, P.FORM_EDIT, workspace.id)
    assert refused.value.status_code == 403
