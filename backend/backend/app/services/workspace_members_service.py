from datetime import timedelta
from http import HTTPStatus
from typing import List, Any
from beanie import PydanticObjectId
from backend.app.exceptions import HTTPException
from backend.app.models.enum.invitation_response import InvitationResponse
from backend.app.models.invitation_request import InvitationRequest
from backend.app.models.workspace_member_dto import WorkspaceMemberDto
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings
from common.constants import MESSAGE_NOT_FOUND
from common.enums.plan import Plans
from common.enums.workspace_invitation_status import InvitationStatus
from common.models.user import User
from datetime import timedelta
from common.services.http_client import HttpClient


class WorkspaceMembersService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        workspace_invitation_repo: WorkspaceInvitationRepo,
        http_client: HttpClient,
        workspace_form_service: WorkspaceFormService
    ):
        self.workspace_user_service = workspace_user_service
        self.workspace_invitation_repository = workspace_invitation_repo
        self.http_client = http_client
        self.workspace_form_service = workspace_form_service

    async def get_workspace_members(self, workspace_id: PydanticObjectId, user: User):
        workspace_users = await self.workspace_user_service.get_users_in_workspace(
            workspace_id=workspace_id, user=user
        )
        user_ids = [user.user_id for user in workspace_users]
        users_info = await self._get_user_info_from_ids(user_ids)
        workspace_users = sorted(workspace_users, key=lambda w_user: w_user.user_id)
        users_info = sorted(users_info, key=lambda u_info: u_info.get("_id"))
        response_user_list = []
        for workspace_user, user_info in zip(workspace_users, users_info):
            user = WorkspaceMemberDto()
            user.id = workspace_user.user_id
            user.first_name = user_info.get("first_name")
            user.last_name = user_info.get("last_name")
            user.email = user_info.get("email")
            user.profile_image = user_info.get("profile_image")
            user.joined = workspace_user.created_at
            user.roles = workspace_user.roles
            response_user_list.append(user)
        return response_user_list

    async def create_invitation_request(
        self, workspace_id: PydanticObjectId, invitation: InvitationRequest, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )

        if user.plan != Plans.PRO:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Upgrade to pro to add collaborators",
            )

        workspace = await WorkspaceDocument.get(workspace_id)

        workspace_invitation = (
            await self.workspace_invitation_repository.create_workspace_invitation(
                workspace_id=workspace_id, invitation=invitation
            )
        )
        await self.http_client.get(
            settings.auth_settings.BASE_URL + "/users/invite/send/mail",
            params={
                "workspace_title": workspace.title,
                "workspace_name": workspace.workspace_name,
                "role": invitation.role.title(),
                "email": invitation.email,
                "token": workspace_invitation.invitation_token,
            },
            timeout=60,
        )
        return workspace_invitation

    async def get_workspace_invitations(
        self, workspace_id: PydanticObjectId, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.workspace_invitation_repository.get_workspace_invitations(
            workspace_id=workspace_id
        )

    async def get_workspace_invitation_by_token(
        self, workspace_id: PydanticObjectId, user: User, invitation_token: str
    ):
        try:
            await self.workspace_user_service.check_user_has_access_in_workspace(
                workspace_id, user
            )
            is_admin = True
        except HTTPException:
            is_admin = False

        invitation = await self.workspace_invitation_repository.get_workspace_invitation_by_token(
            workspace_id=workspace_id, invitation_token=invitation_token
        )
        if invitation is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Invitation not found"
            )
        if (not is_admin) and (user.sub != invitation.email):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Invitation not found"
            )
        return invitation

    async def process_invitation_request(
        self,
        workspace_id: PydanticObjectId,
        invitation_token: str,
        response_status: InvitationResponse,
        user: User,
    ):
        invitation_request = await self.workspace_invitation_repository.get_workspace_invitation_by_token(
            workspace_id=workspace_id, invitation_token=invitation_token
        )
        if not invitation_request:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )

        if invitation_request.email != user.sub:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content="Invalid User"
            )

        if invitation_request.expiry < get_expiry_epoch_after(time_delta=timedelta()):
            invitation_request.invitation_status = InvitationStatus.EXPIRED
            await invitation_request.save()
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Token has expired"
            )
        elif invitation_request.invitation_status != InvitationStatus.PENDING:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, content="Invalid Invitation Token"
            )

        if response_status == InvitationResponse.ACCEPTED:
            invitation_request.invitation_status = InvitationStatus.ACCEPTED
            await self.workspace_user_service.add_user_to_workspace_with_role(
                workspace_id=workspace_id, user=user, role=invitation_request.role
            )

        else:
            invitation_request.invitation_status = InvitationStatus.DECLINED
        await invitation_request.save()

        return "Request Processed Successfully."

    async def _get_user_info_from_ids(
        self, user_ids: List[PydanticObjectId]
    ) -> List[Any]:
        response_data = await self.http_client.get(
            settings.auth_settings.BASE_URL + "/users", params={"user_ids": user_ids}
        )
        return response_data.get("users_info")

    async def delete_workspace_member(self, workspace_id, user_id, user):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id, user
        )
        form_ids_imported_by_user = (
            await self.workspace_form_service.get_form_ids_imported_by_user(
                workspace_id, user_id
            )
        )
        for form_id in form_ids_imported_by_user:
            await self.workspace_form_service.delete_form_from_workspace(
                workspace_id, form_id, user
            )
        await self.workspace_user_service.delete_user_from_workspace(
            workspace_id, user_id
        )
        users_info = await self._get_user_info_from_ids([user_id])
        if users_info:
            await self.workspace_invitation_repository.update_status_to_removed(
                workspace_id, users_info[0].get("email")
            )
        return {"message": "Deleted Successfully"}

    async def delete_workspace_invitation_by_token(self, workspace_id, user, invitation_token):
        await self.workspace_user_service.check_is_admin_in_workspace(workspace_id, user)
        await self.workspace_invitation_repository.delete_invitation_by_token_if_pending_state(invitation_token)
        return {"message": "Invitation deleted successfully."}

