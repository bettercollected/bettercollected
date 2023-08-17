from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User


class WorkspaceUserService:
    def __init__(self, workspace_user_repository: WorkspaceUserRepository):
        self.workspace_user_repository = workspace_user_repository

    async def check_user_has_access_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ):
        workspace = await WorkspaceDocument.find_one({"_id": workspace_id})
        has_access = await self.workspace_user_repository.has_user_access_in_workspace(
            workspace_id, user
        )
        if not has_access or workspace.disabled:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )

    async def check_is_admin_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ):
        workspace = await WorkspaceDocument.find_one({"_id": workspace_id})
        is_admin = await self.workspace_user_repository.is_user_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        if not is_admin or workspace.disabled:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )

    async def get_users_in_workspace(self, workspace_id, user: User):
        await self.check_is_admin_in_workspace(workspace_id=workspace_id, user=user)
        return await self.workspace_user_repository.get_workspace_users(
            workspace_id=workspace_id
        )

    async def add_user_to_workspace_with_role(
        self, workspace_id: PydanticObjectId, user: User, role: WorkspaceRoles
    ):
        existing_user = await WorkspaceUserDocument.find_one(
            {"workspace_id": workspace_id, "user_id": PydanticObjectId(user.id)}
        )
        if existing_user:
            return
        workspace_users = await self.workspace_user_repository.get_workspace_users(
            workspace_id=workspace_id
        )
        if len(workspace_users) > settings.api_settings.ALLOWED_COLLABORATORS:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Cannot import more collaborators",
            )
        workspace_user = WorkspaceUserDocument(
            workspace_id=workspace_id, user_id=user.id, roles=[role]
        )
        return await self.workspace_user_repository.save(workspace_user)

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
