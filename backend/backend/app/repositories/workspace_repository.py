from http import HTTPStatus
from typing import List

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
            raise HTTPException(HTTPStatus.NOT_FOUND)
        return workspace

    async def get_user_workspaces(self, owner_id: str):
        return await WorkspaceDocument.find({"owner_id": owner_id}).to_list()

    async def get_workspace_by_ids(self, workspace_ids: List[PydanticObjectId]):
        return await WorkspaceDocument.find({"_id": {"$in": workspace_ids}}).to_list()

    async def get_workspace_by_owner_id(
        self, owner_id: PydanticObjectId
    ) -> WorkspaceDocument:
        return await WorkspaceDocument.find_one({"ownerId": owner_id})
