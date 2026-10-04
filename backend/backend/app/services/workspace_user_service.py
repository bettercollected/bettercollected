from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from common.models.user import User


class SeatLimitReached(Exception):
    """The workspace has no free seat for another member."""


class WorkspaceUserService:
    def __init__(
        self,
        workspace_user_repository: WorkspaceUserRepository,
        workspace_repo: WorkspaceRepository,
    ):
        self.workspace_user_repository = workspace_user_repository
        self.workspace_repo = workspace_repo

    async def get_users_in_workspace(self, workspace_id):
        return await self.workspace_user_repository.get_workspace_users(
            workspace_id=workspace_id
        )

    async def add_user_to_workspace_with_role(
        self, workspace_id: PydanticObjectId, user: User, role: WorkspaceRoles
    ):
        existing_user = await self.workspace_user_repository.find_workspace_user(
            workspace_id, PydanticObjectId(user.id)
        )
        if existing_user:
            return
        if not await self.has_free_seat(workspace_id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Cannot import more collaborators",
            )
        workspace_user = WorkspaceUserDocument(
            workspace_id=workspace_id, user_id=user.id, roles=[role]
        )
        return await self.workspace_user_repository.save(workspace_user)

    async def has_free_seat(self, workspace_id: PydanticObjectId) -> bool:
        """Whether one more member fits under ``API_ALLOWED_COLLABORATORS``
        (the same count an accepted invitation is checked against)."""
        workspace_users = await self.workspace_user_repository.get_workspace_users(
            workspace_id=workspace_id
        )
        return len(workspace_users) <= settings.api_settings.ALLOWED_COLLABORATORS

    async def find_member(self, workspace_id: PydanticObjectId, user_id: str):
        return await self.workspace_user_repository.find_workspace_user(
            PydanticObjectId(workspace_id), PydanticObjectId(user_id)
        )

    async def add_sso_member(
        self, workspace_id: PydanticObjectId, user: User, role: WorkspaceRoles
    ) -> WorkspaceUserDocument:
        """Just-in-time membership for a single sign-on (docs/sso.md): a new
        member gets ``role``; an existing membership is returned unchanged,
        never downgraded. Raises SeatLimitReached when the workspace is
        full (callers check ``has_free_seat`` before the account is created;
        this is the last look)."""
        existing = await self.find_member(workspace_id, user.id)
        if existing:
            return existing
        if not await self.has_free_seat(workspace_id):
            raise SeatLimitReached(str(workspace_id))
        member = await self.workspace_user_repository.save(
            WorkspaceUserDocument(
                workspace_id=PydanticObjectId(workspace_id),
                user_id=user.id,
                roles=[role],
            )
        )
        # Two sign-ins racing past the look above would both be added: count
        # again after the write and give the seat back when over the cap (in
        # a tight race both may give it back: refusing is the safe side).
        members = await self.workspace_user_repository.get_workspace_users(
            workspace_id=PydanticObjectId(workspace_id)
        )
        if len(members) > settings.api_settings.ALLOWED_COLLABORATORS + 1:
            await self.workspace_user_repository.delete(
                PydanticObjectId(workspace_id), PydanticObjectId(user.id)
            )
            raise SeatLimitReached(str(workspace_id))
        return member

    async def get_mine_workspaces(self, user_id: str):
        workspace_users = await self.workspace_user_repository.get_mine_workspaces(
            user_id=user_id
        )
        return [
            workspace_user.workspace_id
            for workspace_user in workspace_users
            if not workspace_user.disabled
        ]

    async def disable_other_users_in_workspace(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        return await self.workspace_user_repository.disable_other_users_in_workspace(
            workspace_id=workspace_id, user_id=user_id
        )

    async def enable_all_users_in_workspace(self, workspace_id: PydanticObjectId):
        return await self.workspace_user_repository.enable_all_user_in_workspace(
            workspace_id
        )

    async def delete_user_from_workspace(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        return await self.workspace_user_repository.delete(workspace_id, user_id)

    async def delete_user_form_all_workspaces(self, user: User):
        return await self.workspace_user_repository.delete_user_form_all_workspaces(
            user
        )

    async def delete_user_of_workspaces(self, workspace_ids: List[PydanticObjectId]):
        return await self.workspace_user_repository.delete_all_workspaces_users(
            workspace_ids
        )
