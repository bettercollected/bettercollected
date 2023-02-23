from beanie import PydanticObjectId
from classy_fastapi import Routable, get
from fastapi import Depends

from backend.app.container import container
from backend.app.router import router
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.user_service import get_logged_user
from common.models.user import User


@router(
    prefix="/workspaces/{workspace_id}/forms/{form_id}/submissions",
    tags=["Workspace Form Submissions"],
)
class WorkspaceResponsesRouter(Routable):
    def __init__(
        self,
        form_response_service: FormResponseService = container.form_response_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_response_service = form_response_service

    @get("")
    async def _get_workspace_form_responses(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self._form_response_service.get_workspace_submissions(
            workspace_id, form_id, user
        )

    @get("/{submission_id}")
    async def _get_workspace_form_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        submission_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self._form_response_service.get_workspace_submission(
            workspace_id, form_id, submission_id, user
        )
