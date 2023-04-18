from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository

from beanie import PydanticObjectId

from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.constants import MESSAGE_UNAUTHORIZED, MESSAGE_FORBIDDEN
from common.models.user import User


class WorkspaceUserService:
    def __init__(self, workspace_user_repository: WorkspaceUserRepository):
        self.workspace_user_repository = workspace_user_repository

    async def check_user_has_access_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ):
        is_admin = await self.workspace_user_repository.has_user_access_in_workspace(
            workspace_id, user
        )
        if not is_admin:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )

    async def check_is_admin_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ):
        has_access = await self.workspace_user_repository.is_user_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        if not has_access:
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
        workspace_user = WorkspaceUserDocument(
            workspace_id=workspace_id, user_id=user.id, roles=[role]
        )
        return await self.workspace_user_repository.save(workspace_user)
