from typing import List, Any
from datetime import timedelta
from http import HTTPStatus

from beanie import PydanticObjectId
from fastapi_pagination.ext.beanie import paginate

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.workspace_member_dto import WorkspaceMemberDto
from backend.app.models.enum.invitation_response import InvitationResponse
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import (
    ASSIGNABLE_ROLES,
    ROLE_LABELS,
    WorkspaceRoles,
    canonical_role,
    canonical_roles,
    primary_role,
    stored_role,
)
from backend.app.models.invitation_request import InvitationRequest
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from backend.app.services.authorization_service import (
    AuthorizationService,
    role_permissions,
)
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings
from common.constants import MESSAGE_NOT_FOUND, MESSAGE_FORBIDDEN
from common.enums.plan import Plans
from common.enums.workspace_invitation_status import InvitationStatus
from common.models.user import User
from common.services.http_client import HttpClient


class WorkspaceMembersService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        workspace_invitation_repo: WorkspaceInvitationRepo,
        workspace_repo: WorkspaceRepository,
        http_client: HttpClient,
        workspace_form_service: WorkspaceFormService,
        authorization_service: AuthorizationService,
    ):
        self.workspace_user_service = workspace_user_service
        self.authorization_service = authorization_service
        self.workspace_invitation_repository = workspace_invitation_repo
        self.workspace_repo = workspace_repo
        self.http_client = http_client
        self.workspace_form_service = workspace_form_service

    async def get_workspace_members(self, workspace_id: PydanticObjectId, user: User):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        workspace = await self.workspace_repo.find_by_id(workspace_id)
        owner_id = workspace.owner_id if workspace else None
        workspace_users = await self.workspace_user_service.get_users_in_workspace(
            workspace_id=workspace_id
        )
        user_ids = [user.user_id for user in workspace_users]
        users_info = await self._get_user_info_from_ids(user_ids)
        workspace_users = sorted(workspace_users, key=lambda w_user: w_user.user_id)
        users_info = sorted(users_info, key=lambda u_info: u_info.get("_id"))
        response_user_list = []
        for workspace_user, user_info in zip(workspace_users, users_info):
            user = WorkspaceMemberDto()
            user.id = str(workspace_user.user_id)
            user.first_name = user_info.get("first_name")
            user.last_name = user_info.get("last_name")
            user.email = user_info.get("email")
            user.profile_image = user_info.get("profile_image")
            user.joined = workspace_user.created_at
            user.roles = canonical_roles(workspace_user.roles)
            user.role = primary_role(
                workspace_user.roles,
                is_owner=str(workspace_user.user_id) == str(owner_id),
            )
            user.disabled = workspace_user.disabled
            response_user_list.append(user)
        return response_user_list

    async def create_invitation_request(
        self, workspace_id: PydanticObjectId, invitation: InvitationRequest, user: User
    ):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        role = await self._assignable_role(workspace_id, invitation.role, user)

        workspace = await self.workspace_repo.get_or_404(workspace_id)

        workspace_invitation = (
            await self.workspace_invitation_repository.create_workspace_invitation(
                workspace_id=workspace_id,
                invitation=InvitationRequest(
                    email=invitation.email, role=stored_role(role)
                ),
            )
        )
        await self.http_client.get(
            settings.auth_settings.BASE_URL + "/users/invite/send/mail",
            params={
                "workspace_title": workspace.title,
                "workspace_name": workspace.workspace_name,
                "role": ROLE_LABELS[role],
                "email": invitation.email,
                "inviter_id": user.id,
                "token": workspace_invitation.invitation_token,
            },
            headers=auth_service_headers(),
            timeout=60,
        )
        return workspace_invitation

    async def get_workspace_invitations(
        self, workspace_id: PydanticObjectId, user: User
    ):
        # Like the members list: who is invited is for those who manage members.
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        member_invitations = (
            await self.workspace_invitation_repository.get_workspace_invitations(
                workspace_id=workspace_id
            )
        )
        return member_invitations

    async def get_workspace_invitation_by_token(
        self, workspace_id: PydanticObjectId, user: User, invitation_token: str
    ):
        is_admin = await self.authorization_service.has_permission(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        invitation = await self.workspace_invitation_repository.get_workspace_invitation_by_token(
            workspace_id=workspace_id, invitation_token=invitation_token
        )
        if (not is_admin) and not (self.compare_emails(user.sub, invitation.email)):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
        if (not is_admin) and (
            invitation.invitation_status != InvitationStatus.PENDING
            or invitation.expiry < get_expiry_epoch_after(time_delta=timedelta())
        ):
            raise HTTPException(
                status_code=HTTPStatus.GONE, content="This operation is no longer valid"
            )
        return invitation

    def normalize_gmail(self, email):
        local, domain = email.split("@")
        if (
            domain == "gmail.com" or domain == "googlemail.com"
        ):  # Google handles both domains the same
            local = local.replace(".", "")
        return f"{local}@{domain}"

    def compare_emails(self, email1, email2):
        return self.normalize_gmail(email1) == self.normalize_gmail(email2)

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

        if not self.compare_emails(invitation_request.email, user.sub):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content="Invalid User"
            )

        if invitation_request.expiry < get_expiry_epoch_after(time_delta=timedelta()):
            invitation_request.invitation_status = InvitationStatus.EXPIRED
            await self.workspace_invitation_repository.save(invitation_request)
            raise HTTPException(
                status_code=HTTPStatus.GONE, content="Token has expired"
            )
        elif invitation_request.invitation_status != InvitationStatus.PENDING:
            raise HTTPException(
                status_code=HTTPStatus.GONE, content="Invalid Invitation Token"
            )

        if response_status == InvitationResponse.ACCEPTED:
            invitation_request.invitation_status = InvitationStatus.ACCEPTED
            await self.workspace_user_service.add_user_to_workspace_with_role(
                workspace_id=workspace_id, user=user, role=invitation_request.role
            )

        else:
            invitation_request.invitation_status = InvitationStatus.DECLINED
        await self.workspace_invitation_repository.save(invitation_request)
        return "Request Processed Successfully."

    async def _get_user_info_from_ids(
        self, user_ids: List[PydanticObjectId]
    ) -> List[Any]:
        response_data = await self.http_client.get(
            settings.auth_settings.BASE_URL + "/users",
            params={"user_ids": user_ids},
            headers=auth_service_headers(),
        )
        return response_data.get("users_info")

    async def delete_workspace_member(self, workspace_id, user_id, user):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        workspace = await self.workspace_repo.find_by_id(workspace_id)
        if workspace and str(workspace.owner_id) == str(user_id):
            # Ownership can be transferred, never removed.
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="The workspace owner can't be removed.",
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

    async def delete_workspace_invitation_by_token(
        self, workspace_id, user, invitation_token
    ):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        await self.workspace_invitation_repository.delete_invitation_by_token_if_pending_state(
            invitation_token
        )
        return {"message": "Invitation deleted successfully."}

    async def _assignable_role(
        self, workspace_id: PydanticObjectId, role, user: User
    ) -> WorkspaceRoles:
        """``role`` as a role ``user`` may give a member: one of the
        assignable roles (never the owner, which is transferred), and never
        more than ``user`` holds (so an Admin can't promote anyone above
        Admin)."""
        known = canonical_role(role)
        if known not in ASSIGNABLE_ROLES:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Choose Admin, Editor, Reviewer, Viewer or Privacy officer.",
            )
        held = await self.authorization_service.effective_permissions(
            user, workspace_id
        )
        if not role_permissions(known) <= held:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="You can't give a role with more access than your own.",
            )
        return known

    async def update_member_role(
        self,
        workspace_id: PydanticObjectId,
        member_id: PydanticObjectId,
        role: WorkspaceRoles,
        user: User,
    ) -> WorkspaceMemberDto:
        """Give a member another role. Needs members.manage; the owner's role
        never changes (ownership is transferred instead) and no one changes
        their own role."""
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        if str(member_id) == str(user.id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="You can't change your own role.",
            )
        workspace = await self.workspace_repo.get_or_404(workspace_id)
        if str(workspace.owner_id) == str(member_id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="The owner's role can't be changed. Transfer ownership instead.",
            )
        new_role = await self._assignable_role(workspace_id, role, user)
        membership = await self.workspace_user_service.find_workspace_user(
            workspace_id, member_id
        )
        if membership is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Member not found."
            )
        membership.roles = [stored_role(new_role)]
        await self.workspace_user_service.save_workspace_user(membership)
        return WorkspaceMemberDto(
            id=str(member_id),
            roles=canonical_roles(membership.roles),
            role=primary_role(membership.roles),
            disabled=membership.disabled,
        )

    async def transfer_ownership(
        self,
        workspace_id: PydanticObjectId,
        new_owner_id: PydanticObjectId,
        user: User,
    ):
        """Make an active Admin the owner; the old owner stays as an Admin.

        Needs workspace.billing (the owner only). Refused for a personal
        (default) workspace and for one on a paid plan: both are tied to the
        owner's account, not to the workspace (``_refuse_untransferable``).
        """
        await self.authorization_service.authorize(
            user, Permission.WORKSPACE_BILLING, workspace_id
        )
        if str(new_owner_id) == str(user.id):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="You already own this workspace.",
            )
        workspace = await self.workspace_repo.get_or_404(workspace_id)
        self._refuse_untransferable(workspace)
        new_owner = await self.workspace_user_service.find_workspace_user(
            workspace_id, new_owner_id
        )
        if (
            new_owner is None
            or new_owner.disabled
            or WorkspaceRoles.ADMIN
            not in {canonical_role(role) for role in new_owner.roles}
        ):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Ownership can only go to an active Admin of this "
                "workspace. Make them an Admin first.",
            )
        old_owner = await self.workspace_user_service.find_workspace_user(
            workspace_id, PydanticObjectId(user.id)
        )
        # The new owner is written first, then the old one is demoted, so a
        # failure in between leaves an owner and an extra Admin, never a
        # workspace without an owner. Not a transaction: the new owner's
        # membership can still be removed or disabled by another Admin
        # between the check above and this write. The workspace then has an
        # owner without an active membership, who holds nothing (ownership
        # needs one), and the old owner remains an Admin who can invite them
        # back; ownership can't be taken back without another transfer.
        await self.workspace_repo.set_fields(
            workspace, {"owner_id": str(new_owner_id)}
        )
        if old_owner is not None:
            old_owner.roles = [WorkspaceRoles.ADMIN]
            await self.workspace_user_service.save_workspace_user(old_owner)
        return {"message": "Ownership transferred.", "ownerId": str(new_owner_id)}

    @staticmethod
    def _refuse_untransferable(workspace) -> None:
        """Billing and the personal workspace hang off the owner's account.

        - A plan belongs to the owner (``User.plan``, their Stripe
          subscription in the auth service). Upgrades and downgrades find
          the workspaces to change by ``owner_id``, so a paid workspace given
          to someone else would keep its paid features with no one paying,
          and the old owner's later downgrade would no longer reach it.
        - The default workspace is each account's personal one: sign-in
          recreates it (named after the user id) when the account owns none,
          which would collide with the transferred one.
        """
        if workspace.default:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content="This is the owner's personal workspace, which can't "
                "be transferred.",
            )
        if workspace.is_pro:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content="This workspace is on a paid plan billed to the owner's "
                "account, so its ownership can't be transferred.",
            )
