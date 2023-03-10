from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.models.response_dtos import (
    StandardFormResponseCamelModel,
    StandardFormCamelModel,
)
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_UNAUTHORIZED
from common.models.user import User
from common.utils.logger import logger


class FormResponseService:
    def __init__(
        self,
        form_response_repo: FormResponseRepository,
        workspace_form_repo: WorkspaceFormRepository,
        workspace_user_repo: WorkspaceUserRepository,
    ):
        self._form_response_repo = form_response_repo
        self._workspace_form_repo = workspace_form_repo
        self._workspace_user_repo = workspace_user_repo

    async def get_all_workspace_responses(
        self, workspace_id: PydanticObjectId, user: User
    ):
        try:
            if not await self._workspace_user_repo.is_user_admin_in_workspace(
                workspace_id=workspace_id, user=user
            ):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
                )
            form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
                workspace_id=workspace_id
            )
            return await self._form_response_repo.list_by_form_ids(form_ids)
        except Exception as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_user_submissions(self, workspace_id: PydanticObjectId, user: User):
        try:
            form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
                workspace_id
            )
            return await self._form_response_repo.get_user_submissions(
                form_ids=form_ids, user=user
            )
        except Exception as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_workspace_submissions(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        try:
            if not await self._workspace_user_repo.is_user_admin_in_workspace(
                workspace_id, user
            ):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
                )
            workspace_form = (
                await self._workspace_form_repo.get_workspace_form_in_workspace(
                    workspace_id, form_id
                )
            )
            if not workspace_form:
                raise HTTPException(
                    HTTPStatus.NOT_FOUND, "Form not found in the workspace."
                )
            # TODO : Refactor with mongo query instead of python
            form_responses = await self._form_response_repo.list(form_id)
            return form_responses
        except Exception as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_workspace_submission(
        self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        is_admin = self._workspace_user_repo.is_user_admin_in_workspace(
            workspace_id, user
        )
        # TODO : Handle case for multiple form import by other user
        response = await FormResponseDocument.find_one({"response_id": response_id})
        form = await FormDocument.find_one({"form_id": response.form_id})
        workspace_form = await WorkspaceFormDocument.find(
            {
                "workspace_id": workspace_id,
                "form_id": form.form_id,
            }
        ).to_list()
        if not workspace_form:
            raise HTTPException(404, "Form not found in this workspace")

        if not (is_admin or response["dataOwnerIdentifier"] == user.sub):
            raise HTTPException(403, "You are not authorized to perform this action.")

        response = StandardFormResponseCamelModel(**response.dict())
        form = StandardFormCamelModel(**form.dict())

        response.form_title = form.title
        return {"form": form, "response": response}
