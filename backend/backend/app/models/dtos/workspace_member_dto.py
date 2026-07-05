from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel
from pydantic import EmailStr

from backend.app.models.enum.workspace_roles import WorkspaceRoles
from common.enums.workspace_invitation_status import InvitationStatus


class WorkspaceMemberDto(CamelModel):
    id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    profile_image: Optional[str] = None
    joined: Optional[datetime] = None
    roles: Optional[List[WorkspaceRoles]] = None


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
    updated_at: Optional[datetime] = None
    workspace_id: Optional[PydanticObjectId] = None
    id: Optional[PydanticObjectId] = None
