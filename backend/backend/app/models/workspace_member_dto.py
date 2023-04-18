from datetime import datetime
from typing import List, Optional

from backend.app.models.enum.workspace_roles import WorkspaceRoles


class WorkspaceMemberDto:
    id: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    profile_image: Optional[str]
    joined: Optional[datetime]
    roles: Optional[List[WorkspaceRoles]]
