from pydantic import BaseModel, EmailStr

from backend.app.models.enum.workspace_roles import WorkspaceRoles


class InvitationRequest(BaseModel):
    email: EmailStr
    role: WorkspaceRoles
