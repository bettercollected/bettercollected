from typing import List, Any
from datetime import timedelta
from http import HTTPStatus

from beanie import PydanticObjectId

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
    has_owner_role,
    is_billing_owner,
    is_owner_membership,
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
from backend.app.services.workspace_user_service import (
    PROVISIONED_BY_SCIM,
    WorkspaceUserService,
)
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
        scim_directory_repo=None,
    ):
        # a membership the workspace's SCIM directory manages is shown as such
        self._scim_directories = scim_directory_repo
        self.workspace_user_service = workspace_user_service
        self.authorization_service = authorization_service
        self.workspace_invitation_repository = workspace_invitation_repo
        self.workspace_repo = workspace_repo
        self.http_client = http_client
        self.workspace_form_service = workspace_form_service

    async def _has_directory(self, workspace_id) -> bool:
        """The workspace has a SCIM directory (docs/sso.md, "Directory sync")."""
        return (
            self._scim_directories is not None
            and await self._scim_directories.find_by_workspace(workspace_id) is not None
        )

    async def get_workspace_members(self, workspace_id: PydanticObjectId, user: User):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        workspace = await self.workspace_repo.find_by_id(workspace_id)
        workspace_users = await self.workspace_user_service.get_users_in_workspace(
            workspace_id=workspace_id
        )
        user_ids = [user.user_id for user in workspace_users]
        # Joined by user id: the auth service leaves out accounts it no longer
        # has, so pairing two sorted lists would put one person's name on
        # another's membership (and role changes on the wrong person).
        users_by_id = {
            str(info.get("_id")): info
            for info in (await self._get_user_info_from_ids(user_ids) or [])
            if info and info.get("_id") is not None
        }
        has_directory = await self._has_directory(workspace_id)
        response_user_list = []
        for workspace_user in sorted(workspace_users, key=lambda m: str(m.user_id)):
            user_info = users_by_id.get(str(workspace_user.user_id))
            user = WorkspaceMemberDto()
            user.id = str(workspace_user.user_id)
            if user_info is None:
                # a deleted account: listed by id only, clearly marked
                user.account_deleted = True
            else:
                user.first_name = user_info.get("first_name")
                user.last_name = user_info.get("last_name")
                user.email = user_info.get("email")
                user.profile_image = user_info.get("profile_image")
            user.joined = workspace_user.created_at
            is_owner = is_owner_membership(workspace, workspace_user)
            user.roles = canonical_roles(workspace_user.roles)
            user.role = primary_role(workspace_user.roles, is_owner=is_owner)
            user.billing_owner = is_billing_owner(workspace, workspace_user.user_id)
            user.disabled = workspace_user.disabled
            user.provisioned_by = workspace_user.provisioned_by
            # the directory never changes an owner (docs/sso.md)
            user.managed_by_directory = bool(
                has_directory
                and not is_owner
                and workspace_user.provisioned_by == PROVISIONED_BY_SCIM
            )
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
        await self._refuse_existing_member(workspace_id, invitation.email)

        workspace_invitation = (
            await self.workspace_invitation_repository.create_workspace_invitation(
                workspace_id=workspace_id,
                invitation=InvitationRequest(
                    email=invitation.email, role=stored_role(role)
                ),
                invited_by=str(user.id),
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
        # stored as COLLABORATOR for an Editor; reported as EDITOR
        return workspace_invitation.model_copy(update={"role": role})

    async def _refuse_existing_member(self, workspace_id, email: str) -> None:
        """Inviting someone who is already a member would reset their
        accepted invitation to pending; their role is changed instead."""
        memberships = await self.workspace_user_service.get_users_in_workspace(
            workspace_id=workspace_id
        )
        if not memberships:
            return
        users_info = await self._get_user_info_from_ids(
            [membership.user_id for membership in memberships]
        )
        for info in users_info or []:
            if info and info.get("email") and self.compare_emails(info["email"], email):
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    content="This person is already a member; change their role "
                    "instead.",
                )

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
            await self._refuse_if_inviter_lost_the_role(
                workspace_id, invitation_request
            )
            invitation_request.invitation_status = InvitationStatus.ACCEPTED
            await self.workspace_user_service.add_user_to_workspace_with_role(
                workspace_id=workspace_id, user=user, role=invitation_request.role
            )

        else:
            invitation_request.invitation_status = InvitationStatus.DECLINED
        await self.workspace_invitation_repository.save(invitation_request)
        return "Request Processed Successfully."

    async def _refuse_if_inviter_lost_the_role(self, workspace_id, invitation) -> None:
        """An invitation is only as good as its sender: accepting it re-checks
        that they still manage members and still hold every permission of the
        role they gave. Invitations sent before this was recorded carry no
        sender and are not re-checked."""
        if not invitation.invited_by:
            return
        inviter = User(id=str(invitation.invited_by), sub="invitation-sender")
        held = await self.authorization_service.effective_permissions(
            inviter, workspace_id
        )
        if Permission.MEMBERS_MANAGE not in held or not (
            role_permissions(invitation.role) <= held
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="The person who invited you can no longer give this role. "
                "Ask a workspace admin to invite you again.",
            )

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
        if is_billing_owner(workspace, user_id):
            # The workspace runs on their plan: billing moves first.
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="The billing owner can't be removed. Make another owner "
                "the billing owner first.",
            )
        membership = await self.workspace_user_service.find_workspace_user(
            workspace_id, user_id
        )
        if workspace and is_owner_membership(workspace, membership):
            await self._require_owner_to_change_owner(workspace_id, user)
            await self._refuse_leaving_no_owner(workspace, without=user_id)
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
        assignable roles, and never more than ``user`` holds (so only an
        owner makes someone an owner, and an Admin can't promote anyone
        above Admin)."""
        known = canonical_role(role)
        if known not in ASSIGNABLE_ROLES:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Choose Owner, Admin, Editor, Reviewer, Viewer or "
                "Privacy officer.",
            )
        held = await self.authorization_service.effective_permissions(
            user, workspace_id
        )
        if known == WorkspaceRoles.OWNER and not role_permissions(known) <= held:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Only an owner can make someone an owner.",
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
        """Give a member another role. Needs members.manage; no one changes
        their own role. Only an owner makes someone an owner or changes an
        owner's role; the billing owner's role never changes (another owner
        becomes the billing owner first), and the workspace always keeps an
        active owner."""
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        if str(member_id) == str(user.id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="You can't change your own role.",
            )
        workspace = await self.workspace_repo.get_or_404(workspace_id)
        if is_billing_owner(workspace, member_id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="The billing owner's role can't be changed. Make another "
                "owner the billing owner first.",
            )
        membership = await self.workspace_user_service.find_workspace_user(
            workspace_id, member_id
        )
        target_is_owner = is_owner_membership(workspace, membership)
        if target_is_owner:
            await self._require_owner_to_change_owner(workspace_id, user)
        new_role = await self._assignable_role(workspace_id, role, user)
        if membership is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Member not found."
            )
        if target_is_owner and new_role != WorkspaceRoles.OWNER:
            await self._refuse_leaving_no_owner(workspace, without=member_id)
        if (
            membership.provisioned_by == PROVISIONED_BY_SCIM
            and not target_is_owner
            and new_role != WorkspaceRoles.OWNER
            and await self._has_directory(workspace_id)
        ):
            # The directory decides: its group mapping would undo this. It
            # never grants or changes Owner, so making someone an owner (or
            # changing an owner's role) is done here.
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content={
                    "code": "managed_by_directory",
                    "message": "This member's role comes from your directory's "
                    "groups. Change it at your identity provider or in the "
                    "group mapping.",
                },
            )
        membership.roles = [stored_role(new_role)]
        await self.workspace_user_service.save_workspace_user(membership)
        return WorkspaceMemberDto(
            id=str(member_id),
            roles=canonical_roles(membership.roles),
            role=primary_role(membership.roles),
            disabled=membership.disabled,
        )

    async def _require_owner_to_change_owner(self, workspace_id, user: User) -> None:
        """Only an owner demotes or removes another owner."""
        if not await self.authorization_service.is_owner(user, workspace_id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Only an owner can change or remove another owner.",
            )

    async def _refuse_leaving_no_owner(self, workspace, without) -> None:
        """A workspace always keeps at least one active owner: refuse a
        change that would leave none once ``without`` stops being one."""
        for membership in await self.workspace_user_service.get_users_in_workspace(
            workspace_id=workspace.id
        ):
            if (
                str(membership.user_id) != str(without)
                and not membership.disabled
                and is_owner_membership(workspace, membership)
            ):
                return
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            content="A workspace needs at least one active owner. Make someone "
            "else an owner first.",
        )

    async def make_billing_owner(
        self,
        workspace_id: PydanticObjectId,
        new_owner_id: PydanticObjectId,
        user: User,
    ):
        """Make another owner the billing owner (``owner_id``): the account
        whose plan the workspace runs on. The previous billing owner stays an
        owner.

        Needs workspace.billing (any owner). The new billing owner must be an
        active owner already. Refused for a personal (default) workspace and
        for one on a paid plan: both are tied to the billing owner's account,
        not to the workspace (``_refuse_untransferable``).
        """
        await self.authorization_service.authorize(
            user, Permission.WORKSPACE_BILLING, workspace_id
        )
        workspace = await self.workspace_repo.get_or_404(workspace_id)
        previous_id = str(workspace.owner_id)
        if str(new_owner_id) == previous_id:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="They are already the billing owner.",
            )
        self._refuse_untransferable(workspace)
        new_owner = await self.workspace_user_service.find_workspace_user(
            workspace_id, new_owner_id
        )
        if not self._is_active_owner(workspace, new_owner):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Only an active owner of this workspace can become its "
                "billing owner. Make them an owner first.",
            )
        # The previous billing owner stays an owner: their membership gets
        # OWNER *before* owner_id moves, so a failure at any point leaves an
        # extra owner, never a workspace without one.
        previous = await self.workspace_user_service.find_workspace_user(
            workspace_id, PydanticObjectId(previous_id)
        )
        if previous is not None and not has_owner_role(previous.roles):
            previous.roles = [WorkspaceRoles.OWNER]
            await self.workspace_user_service.save_workspace_user(previous)
        # One conditional update (only while owner_id is still the one read
        # above), so two changes can't both land. The target's membership
        # lives in another collection, so it is checked again right after and
        # the change is undone (conditionally) if they stopped being an active
        # owner in between; a change landing after that re-check is not caught.
        changed = await self.workspace_repo.set_owner_if(
            workspace.id, previous_id, str(new_owner_id)
        )
        if changed is None:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content="The workspace's billing owner changed meanwhile. Reload "
                "and try again.",
            )
        if not self._is_active_owner(
            changed,
            await self.workspace_user_service.find_workspace_user(
                workspace_id, new_owner_id
            ),
            by_role=True,
        ):
            await self.workspace_repo.set_owner_if(
                workspace.id, str(new_owner_id), previous_id
            )
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content="They stopped being an active owner meanwhile. The billing "
                "owner was not changed.",
            )
        return {"message": "Billing owner changed.", "ownerId": str(new_owner_id)}

    @staticmethod
    def _is_active_owner(workspace, membership, by_role: bool = False) -> bool:
        """An enabled owner's membership (``by_role``: holding OWNER itself,
        for the re-check once ``owner_id`` already points at them)."""
        if membership is None or membership.disabled:
            return False
        if by_role:
            return has_owner_role(membership.roles)
        return is_owner_membership(workspace, membership)

    @staticmethod
    def _refuse_untransferable(workspace) -> None:
        """Billing and the personal workspace hang off the billing owner's
        account.

        - A plan belongs to the billing owner (``User.plan``, their Stripe
          subscription in the auth service). Upgrades and downgrades find
          the workspaces to change by ``owner_id``, so a paid workspace moved
          to someone else would keep its paid features with no one paying,
          and the old billing owner's later downgrade would no longer reach
          it.
        - The default workspace is each account's personal one: sign-in
          recreates it (named after the user id) when the account owns none,
          which would collide with the transferred one.
        """
        if workspace.default:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content="This is the billing owner's personal workspace, so its "
                "billing owner can't change.",
            )
        if workspace.is_pro:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content="This workspace is on a paid plan billed to the billing "
                "owner's account, so its billing owner can't change.",
            )
