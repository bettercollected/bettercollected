from typing import Optional

from beanie import PydanticObjectId

from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument


class WorkspaceAIProfileRepository:
    async def find_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> Optional[WorkspaceAIProfileDocument]:
        return await WorkspaceAIProfileDocument.find_one({"workspace_id": workspace_id})

    async def save(
        self, document: WorkspaceAIProfileDocument
    ) -> WorkspaceAIProfileDocument:
        return await document.save()
