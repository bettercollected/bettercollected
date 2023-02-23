from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
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

    async def get_workspace_submissions(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        try:
            if not await self._workspace_user_repo.check_user_is_admin_in_workspace(
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
            form_responses = await self._form_response_repo.list(form_id)
            return form_responses
        except Exception as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )
