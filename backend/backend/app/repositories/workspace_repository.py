from http import HTTPStatus
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace import WorkspaceDocument
from common.base.repo import BaseRepository, T, U
from common.enums.form_provider import FormProvider


class WorkspaceRepository(BaseRepository):
    async def list(self) -> List[T]:
        pass

    async def get(self, item_id: str, provider: FormProvider) -> T:
        pass

    async def add(self, item: U | T) -> T:
        pass

    async def delete(self, item_id: str, provider: FormProvider):
        pass

    async def update(
        self, item_id: PydanticObjectId, item: WorkspaceDocument
    ) -> WorkspaceDocument:
        document = await WorkspaceDocument.find_one(WorkspaceDocument.id == item_id)
        if document:
            return await item.save()
        else:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Workspace not found")

    async def get_workspace_by_id(
        self, workspace_id: PydanticObjectId
    ) -> WorkspaceDocument:
        workspace = await WorkspaceDocument.find_one(
            WorkspaceDocument.id == workspace_id
        )
        if not workspace:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        return workspace

    async def find_by_id(self, workspace_id: PydanticObjectId) -> Optional[WorkspaceDocument]:
        return await WorkspaceDocument.find_one({"_id": workspace_id})

    async def find_by_name(self, workspace_name: str) -> Optional[WorkspaceDocument]:
        return await WorkspaceDocument.find_one({"workspace_name": workspace_name})

    async def find_by_custom_domain(self, custom_domain: str) -> Optional[WorkspaceDocument]:
        return await WorkspaceDocument.find_one({"custom_domain": custom_domain})

    async def get_or_404(self, workspace_id: PydanticObjectId) -> WorkspaceDocument:
        """Like ``find_by_id`` but raises the document layer's NotFoundError when missing."""
        return await WorkspaceDocument.get(workspace_id)

    async def save(self, workspace: WorkspaceDocument) -> WorkspaceDocument:
        return await workspace.save()

    async def set_fields(self, workspace: WorkspaceDocument, fields: Dict[str, Any]) -> None:
        await workspace.update({"$set": fields})

    async def get_workspace_by_query(self, query: str):
        workspace = await WorkspaceDocument.find_one(
            {
                "$or": [
                    {"workspace_name": query},
                    {
                        "$and": [
                            {"custom_domain": query},
                            {
                                "$or": [
                                    {"custom_domain_disabled": {"$exists": False}},
                                    {"custom_domain_disabled": False},
                                ]
                            },
                        ]
                    },
                ]
            }
        )
        if not workspace:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                content="The page you are looking is unavailable.",
            )
        return workspace

    async def get_user_workspaces(self, owner_id: str):
        return await WorkspaceDocument.find({"owner_id": owner_id}).to_list()

    async def get_workspace_by_ids(self, workspace_ids: List[PydanticObjectId]):
        return await WorkspaceDocument.find({"_id": {"$in": workspace_ids}}).to_list()

    async def get_default_workspace_by_owner_id(
        self, owner_id: str
    ) -> WorkspaceDocument:
        return await WorkspaceDocument.find_one({"owner_id": owner_id, "default": True})

    async def delete_workspaces_with_ids(self, workspace_ids: List[PydanticObjectId]):
        return await WorkspaceDocument.find({"_id": {"$in": workspace_ids}}).delete()

    async def get_workspace_with_action_by_id(
        self, workspace_id: PydanticObjectId, action_id: PydanticObjectId
    ):
        workspaces = (
            await WorkspaceDocument.find({"_id": workspace_id})
            .aggregate(
                [
                    {
                        "$lookup": {
                            "from": "workspace_actions",
                            "localField": "_id",
                            "foreignField": "workspace_id",
                            "as": "actions",
                        }
                    },
                    {"$unwind": "$actions"},
                    {"$match": {"actions.action_id": action_id}},
                    {
                        "$set": {
                            f"parameters.{action_id}": "$actions.parameters",
                            f"secrets.{action_id}": "$actions.secrets",
                            "id": workspace_id,
                        }
                    },
                    {"$unset": "actions"},
                ]
            )
            .to_list()
        )
        if len(workspaces) == 0:
            raise HTTPException(status_code=404, content="Workspace not found")
        return workspaces[0]
