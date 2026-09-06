from typing import List, Optional

from beanie import PydanticObjectId

from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument


class WorkspaceAPIKeyRepository:
    async def save(self, document: WorkspaceAPIKeyDocument) -> WorkspaceAPIKeyDocument:
        return await document.save()

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceAPIKeyDocument]:
        return await WorkspaceAPIKeyDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    async def get_or_404(self, key_id: PydanticObjectId) -> WorkspaceAPIKeyDocument:
        """Raises the document layer's NotFoundError when missing, like Document.get."""
        return await WorkspaceAPIKeyDocument.get(key_id)

    async def find_by_key_hash(
        self, key_hash: str
    ) -> Optional[WorkspaceAPIKeyDocument]:
        return await WorkspaceAPIKeyDocument.find_one({"key_hash": key_hash})
