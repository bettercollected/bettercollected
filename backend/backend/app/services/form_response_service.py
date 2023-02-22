from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.models.user import User
from common.utils.logger import logger


class FormResponseService:
    def __init__(
        self,
        form_response_repo: FormResponseRepository,
        workspace_form_repo: WorkspaceFormRepository,
    ):
        self._form_response_repo = form_response_repo
        self._workspace_form_repo = workspace_form_repo

    async def get_workspace_submissions(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        try:
            # TODO: check user is in admin in workspace
            workspace_form = (
                await self._workspace_form_repo.get_workspace_form_in_workspace(
                    workspace_id, form_id
                )
            )
            if not workspace_form:
                raise HTTPException(
                    HTTPStatus.NOT_FOUND, "Form not found in the workspace."
                )
            form_responses = await self._form_response_repo.list(form_id)
            return form_responses
        except Exception as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )
