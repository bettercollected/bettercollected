from beanie import PydanticObjectId

from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.exceptions.http import HTTPException


class WorkspaceFormRepository:
    async def get_workspace_form_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str, throw_if_absent=True
    ):
        workspace_form = await WorkspaceFormDocument.find_one(
            {"id": workspace_id, "form_id": form_id}
        )
        if not workspace_form and throw_if_absent:
            raise HTTPException(404, "Form not found in workspace.")

    async def get_form_ids_in_workspace(
        self, workspace_id: PydanticObjectId, public_only: bool = False
    ):
        query = {"workspace_id": workspace_id}
        if public_only:
            query["settings.private"] = False
        workspace_forms = (
            await WorkspaceFormDocument.find(query)
            .aggregate([{"$project": {"formId": 1, "_id": 0}}])
            .to_list()
        )
        return [a["formId"] for a in workspace_forms]
