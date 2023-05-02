from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.models.user import User


class WorkspaceUserRepository:
    async def has_user_access_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ) -> bool:
        if not user or not workspace_id:
            return False
        workspace_user = await WorkspaceUserDocument.find_one(
            {
                "workspace_id": PydanticObjectId(workspace_id),
                "user_id": PydanticObjectId(user.id),
            }
        )
        return True if workspace_user and not workspace_user.disabled else False

    async def is_user_admin_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
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

    async def get_workspace_users(self, workspace_id: PydanticObjectId):
        return await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    async def save(self, workspace_user: WorkspaceUserDocument):
        return await workspace_user.save()

    async def disable_other_users_in_workspace(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        workspace_users = await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()
        for workspace_user in workspace_users:
            if workspace_user.user_id != user_id:
                workspace_user.disabled = True
                await workspace_user.save()

    async def enable_all_user_in_workspace(self, workspace_id: PydanticObjectId):
        return await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).update_many({"$set": {"disabled": False}})

    async def delete(self, workspace_id, user_id):
        workspace_user = await WorkspaceUserDocument.find_one(
            {
                "workspace_id": PydanticObjectId(workspace_id),
                "user_id": PydanticObjectId(user_id),
            }
        )
        if not workspace_user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Resource doesn't exist"
            )
        return await WorkspaceUserDocument.delete(workspace_user)

    async def get_mine_workspaces(self, user_id: str):
        return await WorkspaceUserDocument.find(
            {"user_id": PydanticObjectId(user_id)}
        ).to_list()
