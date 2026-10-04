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
    # the one role to show: OWNER, ADMIN, EDITOR, REVIEWER, VIEWER,
    # PRIVACY_OFFICER, or None for a role this release doesn't know
    role: Optional[str] = None
    disabled: Optional[bool] = None


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
    role: Optional[WorkspaceRoles] = None

    @field_validator("role")
    @classmethod
    def _editor_not_collaborator(cls, role):
        # invitations store an Editor as COLLABORATOR; the API says EDITOR
        return canonical_role(role) if role is not None else role

    updated_at: Optional[datetime] = None
    workspace_id: Optional[PydanticObjectId] = None
    id: Optional[PydanticObjectId] = None
