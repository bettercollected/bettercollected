from beanie import PydanticObjectId

from backend.app.models.enum.invitation_response import InvitationResponse
from backend.app.models.invitation_request import InvitationRequest
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.services.workspace_user_service import WorkspaceUserService
from common.models.user import User


class WorkspaceMembersService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        workspace_invitation_repo: WorkspaceInvitationRepo,
    ):
        self.workspace_user_service = workspace_user_service
        self.workspace_invitation_repository = workspace_invitation_repo

    async def get_workspace_members(self, workspace_id: PydanticObjectId, user: User):
        return await self.workspace_user_service.get_users_in_workspace(
            workspace_id=workspace_id, user=user
        )

    async def create_invitation_request(
        self, workspace_id: PydanticObjectId, invitation: InvitationRequest, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.workspace_invitation_repository.create_workspace_invitation(
            workspace_id=workspace_id, invitation=invitation
        )

    async def get_workspace_invitations(
        self, workspace_id: PydanticObjectId, invitation_id: str, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        if not invitation_id:
            return await self.workspace_invitation_repository.get_workspace_invitations(
                workspace_id=workspace_id
            )

    async def process_invitation_request(
        self,
        workspace_id: PydanticObjectId,
        invitation_token: str,
        response_status: InvitationResponse,
    ):
        pass
