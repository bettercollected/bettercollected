from datetime import datetime
from typing import List, Optional

from fastapi_camelcase import CamelModel

from backend.app.models.enum.workspace_roles import WorkspaceRoles


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
