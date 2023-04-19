from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument

from beanie import PydanticObjectId

from backend.app.models.enum.workspace_roles import WorkspaceRoles
from common.models.user import User


class WorkspaceUserRepository:
    @staticmethod
    async def has_user_access_in_workspace(
        workspace_id: PydanticObjectId, user: User
    ) -> bool:
        if not user or not workspace_id:
            return False
        workspace_user = await WorkspaceUserDocument.find_one(
            {
                "workspace_id": PydanticObjectId(workspace_id),
                "user_id": PydanticObjectId(user.id),
            }
        )
        return True if workspace_user else False

    @staticmethod
    async def is_user_admin_in_workspace(
        workspace_id: PydanticObjectId, user: User
    ) -> bool:
        if not user or not workspace_id:
            return False
        workspace_user = await WorkspaceUserDocument.find_one(
            {
                "workspace_id": PydanticObjectId(workspace_id),
                "user_id": PydanticObjectId(user.id),
            }
        )
        workspace = await WorkspaceDocument.get(workspace_id)
        return (
            True
            if workspace_user
            and (
                WorkspaceRoles.ADMIN in workspace_user.roles
                or workspace.owner_id == user.id
            )
            else False
        )

    @staticmethod
    async def get_workspace_users(workspace_id: PydanticObjectId):
        return await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()
