from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from common.constants import MESSAGE_UNAUTHORIZED
from common.models.user import User


class WorkspaceUserService:

    def __init__(self, workspace_user_repository: WorkspaceUserRepository):
        self.workspace_user_repository = workspace_user_repository

    async def check_user_is_admin_in_workspace(
            self,
            workspace_id: PydanticObjectId, user: User
    ):
        is_admin = await self.workspace_user_repository.is_user_admin_in_workspace(workspace_id, user)
        if not is_admin:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
            )
