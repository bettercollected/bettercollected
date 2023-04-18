from beanie import PydanticObjectId
from fastapi_pagination import paginate

from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument


class WorkspaceInvitationRepo:
    async def create_workspace_invitation(
        self, workspace_id: PydanticObjectId, invitation: InvitationRequest
    ):
        invitation_request = WorkspaceUserInvitesDocument(
            workspace_id=workspace_id, email=invitation.email, role=invitation.role
        )
        await invitation_request.save()

    async def get_workspace_invitations(self, workspace_id: PydanticObjectId):
        invitations_query = WorkspaceUserInvitesDocument.find(
            {"workspace_id": workspace_id}
        ).aggregate()
        return paginate(invitations_query)
