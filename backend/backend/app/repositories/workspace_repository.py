from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId

from backend.app.schemas.workspace import WorkspaceDocument
from common.base.repo import BaseRepository, U, T
from common.enums.form_provider import FormProvider
from common.exceptions.http import HTTPException


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

    async def get_workspace_by_id(self, workspace_id: PydanticObjectId) -> WorkspaceDocument:
        return await WorkspaceDocument.find_one(WorkspaceDocument.id == workspace_id)

    async def get_workspace_by_query(self, query: str):
        workspace = await WorkspaceDocument.find_one(
            {"$or": [{"workspaceName": query}, {"customDomain": query}]}
        )
        if not workspace:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        return workspace

    async def get_user_workspaces(self, owner_id: str):
        return await WorkspaceDocument.find({"ownerId": owner_id}).to_list()
