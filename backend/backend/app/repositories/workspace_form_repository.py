from http import HTTPStatus

from beanie import PydanticObjectId
from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)

from backend.app.exceptions import HTTPException
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_NOT_FOUND


class WorkspaceFormRepository:

    async def save_workspace_form(self,
                                  workspace_id: PydanticObjectId,
                                  form_id: str,
                                  user_id: str,
                                  workspace_form_settings: WorkspaceFormSettings
                                  ):
        workspace_form = await WorkspaceFormDocument.find_one({
            "workspace_id": workspace_id,
            "form_id": form_id,
            "user_id": user_id})
        if not workspace_form:
            workspace_form = WorkspaceFormDocument(
                workspace_id=workspace_id,
                form_id=form_id,
                user_id=user_id,
            )
        workspace_form.settings = workspace_form_settings
        await workspace_form.save()

    # TODO : Refactor this functions  to include repo related only not related to services
    async def get_workspace_form_in_workspace(
            self,
            workspace_id: PydanticObjectId,
            query: str,
            throw_if_absent=True,
            is_admin=True,
    ):
        try:
            query = {
                "workspace_id": workspace_id,
                "$or": [{"form_id": query}, {"settings.custom_url": query}],
            }
            if not is_admin:
                query["settings.private"] = False

            workspace_form = await WorkspaceFormDocument.find_one(query)
            if not workspace_form and throw_if_absent:
                raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)

            return workspace_form
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_form_ids_in_workspace(
            self, workspace_id: PydanticObjectId, public_only: bool = False
    ):
        try:
            query = {"workspace_id": workspace_id}
            if public_only:
                query["settings.private"] = False
            workspace_forms = (
                await WorkspaceFormDocument.find(query)
                    .aggregate([{"$project": {"form_id": 1, "_id": 0}}])
                    .to_list()
            )
            return [a["form_id"] for a in workspace_forms]
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )
