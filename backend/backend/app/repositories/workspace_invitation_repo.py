import secrets
from datetime import timedelta
from http import HTTPStatus

from beanie import PydanticObjectId
from fastapi_pagination.ext.beanie import paginate

from backend.app.exceptions import HTTPException
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from common.enums.workspace_invitation_status import InvitationStatus


class WorkspaceInvitationRepo:
    async def create_workspace_invitation(
        self, workspace_id: PydanticObjectId, invitation: InvitationRequest
    ):
        existing_invitation = await WorkspaceUserInvitesDocument.find_one(
            {"workspace_id": workspace_id, "email": invitation.email}
        )
        if existing_invitation:
            existing_invitation.invitation_status = InvitationStatus.PENDING
            existing_invitation.expiry = get_expiry_epoch_after(
                time_delta=timedelta(days=7)
            )
            existing_invitation.invitation_token = secrets.token_hex(16)
        else:
            existing_invitation = WorkspaceUserInvitesDocument(
                workspace_id=workspace_id,
                email=invitation.email,
                role=invitation.role,
                invitation_token=secrets.token_hex(16),
            )
        return await existing_invitation.save()

    async def get_workspace_invitations(self, workspace_id: PydanticObjectId):
        invitations_query = WorkspaceUserInvitesDocument.find(
            {"workspace_id": workspace_id}
        )
        return await paginate(invitations_query)

    async def get_workspace_invitation_by_token(
        self, workspace_id: PydanticObjectId, invitation_token: str, is_admin=False
    ) -> WorkspaceUserInvitesDocument | None:
        invitation_request = await WorkspaceUserInvitesDocument.find_one(
            {"invitation_token": invitation_token, "workspace_id": workspace_id}
        )

        if not is_admin and (
            invitation_request.invitation_status != InvitationStatus.PENDING
            or invitation_request.expiry
            < get_expiry_epoch_after(time_delta=timedelta())
        ):
            return None

        return invitation_request

    async def delete_invitation_by_token_if_pending_state(self, invitation_token):
        invitation_request = await WorkspaceUserInvitesDocument.find_one(
            {"invitation_token": invitation_token}
        )
        if not invitation_request:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Invitation not found")
        elif invitation_request.invitation_status == InvitationStatus.PENDING:
            await WorkspaceUserInvitesDocument.delete(invitation_request)
        else:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY, "Invitation not in pending state"
            )

    async def update_status_to_removed(
        self, workspace_id: PydanticObjectId, email: str
    ):
        await WorkspaceUserInvitesDocument.find_one(
            {"workspace_id": workspace_id, "email": email}
        ).update({"$set": {"invitation_status": InvitationStatus.REMOVED}})
