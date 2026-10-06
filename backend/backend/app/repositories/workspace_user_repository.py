from http import HTTPStatus
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import has_owner_role
from backend.app.schemas.workspace_user import (
    DISABLED_BY_PLAN,
    WorkspaceUserDocument,
)
from common.db.routing import write_op


class WorkspaceUserRepository:
    async def get_workspace_users(self, workspace_id: PydanticObjectId):
        return await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    async def find_workspace_user(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> Optional[WorkspaceUserDocument]:
        return await WorkspaceUserDocument.find_one(
            {"workspace_id": workspace_id, "user_id": user_id}
        )

    @write_op
    async def save(self, workspace_user: WorkspaceUserDocument):
        return await workspace_user.save()

    @write_op(replay=True)
    async def add_if_absent(
        self, workspace_user: WorkspaceUserDocument
    ) -> WorkspaceUserDocument:
        """Insert a new membership, or return the one the workspace already
        has for that user (the unique index on workspace and user decides a
        race)."""
        try:
            return await workspace_user.insert()
        except DuplicateKeyError:
            existing = await WorkspaceUserDocument.find_one(
                {
                    "workspace_id": workspace_user.workspace_id,
                    "user_id": workspace_user.user_id,
                }
            )
            if existing is None:
                raise
            return existing

    @write_op
    async def disable_other_users_in_workspace(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        """The billing owner's plan lapsed: disable every member but
        ``user_id`` (the billing owner) and the other owners, who keep the
        same read-only access to the disabled workspace."""
        workspace_users = await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()
        for workspace_user in workspace_users:
            if (
                workspace_user.user_id != user_id
                and not has_owner_role(workspace_user.roles)
                and workspace_user.disable_for(DISABLED_BY_PLAN)
            ):
                await workspace_user.save()

    @write_op
    async def enable_all_user_in_workspace(self, workspace_id: PydanticObjectId):
        """Lifts the plan's reason only: a member the directory deactivated
        stays disabled."""
        enabled = 0
        for workspace_user in await WorkspaceUserDocument.find(
            {"workspace_id": workspace_id}
        ).to_list():
            if workspace_user.enable_for(DISABLED_BY_PLAN):
                await workspace_user.save()
                enabled += 1
        return enabled

    @write_op
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

    @write_op
    async def delete_user_form_all_workspaces(self, user):
        return await WorkspaceUserDocument.find(
            {"user_id": PydanticObjectId(user.id)}
        ).delete()

    @write_op
    async def delete_all_workspaces_users(self, workspaces_ids: List[PydanticObjectId]):
        return await WorkspaceUserDocument.find(
            {"workspace_id": {"$in": workspaces_ids}}
        ).delete()
