from typing import Any, Union

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, post, delete
from fastapi import Depends
from fastapi_pagination import Page

from backend.app.container import container
from backend.app.models.enum.invitation_response import InvitationResponse
from backend.app.models.invitation_request import InvitationRequest
from backend.app.router import router
from backend.app.services.user_service import get_logged_user
from backend.app.services.workspace_members_service import WorkspaceMembersService
from common.models.user import User


@router(
    prefix="/workspaces/{workspace_id}/members",
    tags=["Workspace Members and Invitations"],
)
class WorkspaceMembersRouter(Routable):
    def __init__(
        self,
        workspace_members_service: WorkspaceMembersService = container.workspace_members_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.workspace_members_service = workspace_members_service

    @get("")
    async def get_workspace_members(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.workspace_members_service.get_workspace_members(
            workspace_id=workspace_id, user=user
        )

    @delete("/{user_id}")
    async def delete_workspace_member(
        self,
        workspace_id: PydanticObjectId,
        user_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_members_service.delete_workspace_member(
            workspace_id=workspace_id, user_id=user_id, user=user
        )

    @get("/invitations", response_model=Page[Any])
    async def get_workspace_invitations(
        self,
        workspace_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_members_service.get_workspace_invitations(
            workspace_id=workspace_id, user=user
        )

    @post("/invitations")
    async def create_a_workspace_invitation(
        self,
        workspace_id: PydanticObjectId,
        invitation: InvitationRequest,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_members_service.create_invitation_request(
            workspace_id=workspace_id, invitation=invitation, user=user
        )

    @get("/invitations/{invitation_token}")
    async def get_invitation_by_token(
        self,
        workspace_id: PydanticObjectId,
        invitation_token: str,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_members_service.get_workspace_invitation_by_token(
            workspace_id=workspace_id, user=user, invitation_token=invitation_token
        )

    @delete("/invitations/{invitation_token}")
    async def delete_invitation_by_token(
        self,
        workspace_id: PydanticObjectId,
        invitation_token: str,
        user: User = Depends(get_logged_user),
    ):
        return (
            await self.workspace_members_service.delete_workspace_invitation_by_token(
                workspace_id=workspace_id, user=user, invitation_token=invitation_token
            )
        )

    @post("/invitations/{invitation_token}")
    async def respond_to_invitation_request(
        self,
        workspace_id: PydanticObjectId,
        invitation_token: str,
        response_status: InvitationResponse,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_members_service.process_invitation_request(
            workspace_id=workspace_id,
            invitation_token=invitation_token,
            response_status=response_status,
            user=user,
        )
