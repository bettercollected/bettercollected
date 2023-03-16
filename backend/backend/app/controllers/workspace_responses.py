from beanie import PydanticObjectId
from classy_fastapi import Routable, delete, get
from fastapi import Depends

from backend.app.container import container
from backend.app.models.response_dtos import StandardFormResponseCamelModel
from backend.app.router import router
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.user_service import get_logged_user
from backend.app.utils.custom_routable import CustomRoutable
from common.models.user import User


@router(
    prefix="/workspaces/{workspace_id}",
    tags=["Workspace Form Submissions"],
)
class WorkspaceResponsesRouter(CustomRoutable):
    def __init__(
            self,
            form_response_service: FormResponseService = container.form_response_service(),
            *args,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_response_service = form_response_service

    @get("/forms/{form_id}/submissions")
    async def _get_workspace_form_responses(
            self,
            workspace_id: PydanticObjectId,
            form_id: str,
            request_for_deletion: bool = False,
            user: User = Depends(get_logged_user),
    ):
        responses = await self._form_response_service.get_workspace_submissions(
            workspace_id, request_for_deletion, form_id, user
        )

        return [
            StandardFormResponseCamelModel(**response.dict()) for response in responses
        ]

    @get("/allSubmissions")
    async def _get_all_workspace_responses(
            self,
            workspace_id: PydanticObjectId,
            request_for_deletion: bool = False,
            user=Depends(get_logged_user),
    ):
        responses = await self._form_response_service.get_all_workspace_responses(
            workspace_id, request_for_deletion, user
        )
        return responses

    @get("/submissions")
    async def _get_user_submissions_in_workspace(
            self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        submissions = await self._form_response_service.get_user_submissions(
            workspace_id, user
        )
        return submissions

    # TODO : Insert form id here/ Make uniform endpoints
    @get("/submissions/{submission_id}")
    async def _get_workspace_form_response(
            self,
            workspace_id: PydanticObjectId,
            submission_id: str,
            user: User = Depends(get_logged_user),
    ):
        return await self._form_response_service.get_workspace_submission(
            workspace_id, submission_id, user
        )

    @delete("/submissions/{submission_id}")
    async def _request_workspace_form_response_delete(
            self,
            workspace_id: PydanticObjectId,
            submission_id: str,
            user: User = Depends(get_logged_user),
    ):
        await self._form_response_service.request_for_response_deletion(
            workspace_id, submission_id, user
        )
        return {"message": "Request for deletion created successfully."}
