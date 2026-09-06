from typing import Optional

from beanie import PydanticObjectId

from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from common.db.routing import write_op


class WorkspaceAIProfileRepository:
    async def find_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> Optional[WorkspaceAIProfileDocument]:
        return await WorkspaceAIProfileDocument.find_one({"workspace_id": workspace_id})

    @write_op
    async def save(
        self, document: WorkspaceAIProfileDocument
    ) -> WorkspaceAIProfileDocument:
        return await document.save()
