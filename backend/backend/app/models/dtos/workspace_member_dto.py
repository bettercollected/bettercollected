from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel
from pydantic import EmailStr

from backend.app.models.enum.workspace_roles import WorkspaceRoles
from common.enums.workspace_invitation_status import InvitationStatus


class WorkspaceMemberDto(CamelModel):
    id: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    profile_image: Optional[str]
    joined: Optional[datetime]
    roles: Optional[List[WorkspaceRoles]]


class FormImporterDetails(CamelModel):
    id: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    profile_image: Optional[str]


class WorkspaceInvitationDto(CamelModel):
    created_at: Optional[datetime]
    email: Optional[EmailStr]
    expiry: Optional[int]
    invitation_status: Optional[InvitationStatus]
    invitation_token: Optional[str]
    role: Optional[WorkspaceRoles]
    updated_at: Optional[datetime]
    workspace_id: Optional[PydanticObjectId]
    id: Optional[PydanticObjectId]
