from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.schemas.workspace import WorkspaceDocument
from common.base.repo import BaseRepository
from common.exceptions.http import HTTPException


class WorkspaceRepository(BaseRepository):
    async def update(
        self, item_id: PydanticObjectId, item: WorkspaceDocument
    ) -> WorkspaceDocument:
        document = await WorkspaceDocument.find_one(WorkspaceDocument.id == item_id)
        if document:
            return await item.save()
        else:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Workspace not found")

    async def get_workspace_by_id(self, workspace_id) -> WorkspaceDocument:
        return await WorkspaceDocument.find_one({"_id": workspace_id})

    async def get_workspace_by_query(self, query: str):
        return await WorkspaceDocument.find_one(
            {"$or": [{"workspace_name": query}, {"custom_domain": query}]}
        )
