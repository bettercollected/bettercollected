from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel
from pydantic import EmailStr, field_validator

from backend.app.models.enum.workspace_roles import WorkspaceRoles, canonical_role
from common.enums.workspace_invitation_status import InvitationStatus


class WorkspaceMemberDto(CamelModel):
    id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    profile_image: Optional[str] = None
    joined: Optional[datetime] = None
    # the stored roles as the API names them (COLLABORATOR is EDITOR)
    roles: Optional[List[str]] = None
    # the auth service no longer knows this account (deleted): only the id
    # is known, never someone else's name or email
    account_deleted: Optional[bool] = None
    # the one role to show: OWNER, ADMIN, EDITOR, REVIEWER, VIEWER,
    # PRIVACY_OFFICER, or None for a role this release doesn't know
    role: Optional[str] = None
    disabled: Optional[bool] = None
    # "sso" (just in time), "scim" (the directory) or None (invited)
    provisioned_by: Optional[str] = None
    # the workspace's SCIM directory controls this member's role and status
    managed_by_directory: bool = False


class UpdateMemberRoleRequest(CamelModel):
    role: WorkspaceRoles


class FormImporterDetails(CamelModel):
    id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    profile_image: Optional[str] = None


class WorkspaceInvitationDto(CamelModel):
    created_at: Optional[datetime] = None
    email: Optional[EmailStr] = None
    expiry: Optional[int] = None
    invitation_status: Optional[InvitationStatus] = None
    invitation_token: Optional[str] = None
    role: Optional[str] = None

    @field_validator("role", mode="before")
    @classmethod
    def _editor_not_collaborator(cls, role):
        # invitations store an Editor as COLLABORATOR; the API says EDITOR.
        # A role this release doesn't know is reported as it is.
        if role is None:
            return role
        known = canonical_role(role)
        return known.value if known else str(role)

    updated_at: Optional[datetime] = None
    workspace_id: Optional[PydanticObjectId] = None
    id: Optional[PydanticObjectId] = None
