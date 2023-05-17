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
from common.models.user import User


class WorkspaceFormRepository:
    async def update(
        self, item_id: str, item: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        workspace_form = await WorkspaceFormDocument.find_one(
            WorkspaceFormDocument.id == item_id
        )
        if not workspace_form:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in ")
        return await item.save()

    async def save_workspace_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user_id: str,
        workspace_form_settings: WorkspaceFormSettings,
    ):
        workspace_form = await WorkspaceFormDocument.find_one(
            {"workspace_id": workspace_id, "form_id": form_id, "user_id": user_id}
        )
        if not workspace_form:
            workspace_form = WorkspaceFormDocument(
                workspace_id=workspace_id,
                form_id=form_id,
                user_id=user_id,
            )
        workspace_form.settings = workspace_form_settings
        await workspace_form.save()

    # TODO : Refactor this functions to include repo related only
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
        self,
        workspace_id: PydanticObjectId,
        is_not_admin: bool = False,
        user: User = None,
    ):
        try:
            query = {"workspace_id": workspace_id}
            aggregation_pipeline = []
            if is_not_admin and user:
                aggregation_pipeline.extend(
                    [
                        {
                            "$lookup": {
                                "from": "responder_group_form",
                                "localField": "form_id",
                                "foreignField": "form_id",
                                "as": "groups",
                            }
                        },
                        {
                            "$lookup": {
                                "from": "responder_group_email",
                                "localField": "groups.group_id",
                                "foreignField": "group_id",
                                "as": "emails",
                            }
                        },
                        {"$match": {"emails.email": user.sub}},
                    ]
                )
                pass
            aggregation_pipeline.extend([{"$project": {"form_id": 1, "_id": 0}}])
            workspace_forms = (
                await WorkspaceFormDocument.find(query)
                .aggregate(aggregation_pipeline)
                .to_list()
            )
            return [a["form_id"] for a in workspace_forms]
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_workspace_form_with_custom_slug(
        self, workspace_id: PydanticObjectId, custom_url: str
    ):
        return await WorkspaceFormDocument.find_one(
            {"workspace_id": workspace_id, "settings.custom_url": custom_url}
        )

    async def get_workspace_ids_for_form_id(self, form_id):
        workspace_forms = await WorkspaceFormDocument.find(
            {"form_id": form_id}
        ).to_list()
        return [workspace_form.workspace_id for workspace_form in workspace_forms]

    async def delete_form_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        workspace_form = await WorkspaceFormDocument.find_one(
            {"form_id": form_id, "workspace_id": workspace_id}
        )
        if not workspace_form:
            raise HTTPException(status_code=404, content="Form not found in Workspace")
        await workspace_form.delete()
        return workspace_form

    async def check_is_form_imported_in_other_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        workspace_forms = await WorkspaceFormDocument.find(
            {"form_id": form_id}
        ).to_list()
        if len(workspace_forms) != 0:
            for workspace_form in workspace_forms:
                if workspace_form.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=HTTPStatus.CONFLICT,
                        content="Form has already been imported to another workspace",
                    )

    async def get_form_ids_imported_by_user(
        self, workspace_id: PydanticObjectId, user_id: str
    ):
        forms = await WorkspaceFormDocument.find(
            {"workspace_id": workspace_id, "user_id": user_id}
        ).to_list()
        return [form.form_id for form in forms]
