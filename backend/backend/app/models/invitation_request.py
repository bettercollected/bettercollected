from pydantic import BaseModel

from backend.app.models.enum.workspace_roles import WorkspaceRoles


class InvitationRequest(BaseModel):
    email: str
    role: WorkspaceRoles
