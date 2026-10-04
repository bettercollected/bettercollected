"""The permission catalogue, today's role mapping and the authorization
service's rules (docs/enterprise-access-model.md, step a)."""

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
    MEMBER_PERMISSIONS,
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


def test_a_collaborator_is_the_editor_plus_todays_privacy_work():
    granted = permissions_for([WorkspaceRoles.COLLABORATOR], is_owner=False)
    assert granted == EDITOR_PERMISSIONS | {P.PRIVACY_MANAGE}
    for workspace_level in (
        P.WORKSPACE_MANAGE,
        P.WORKSPACE_BILLING,
        P.MEMBERS_MANAGE,
        P.SECURITY_MANAGE,
        P.AI_MANAGE,
        P.AUDIT_READ,
    ):
        assert workspace_level not in granted


@pytest.mark.parametrize("roles", [[], ["FORM_CREATOR"], None])
def test_any_active_membership_is_a_member(roles):
    """Today every active membership has member access, whatever its roles."""
    assert permissions_for(roles, is_owner=False) == MEMBER_PERMISSIONS


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
