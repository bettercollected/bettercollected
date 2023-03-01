from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, get
from fastapi import Depends

from backend.app.container import container
from backend.app.models.generic_models import (
    GenericResponseModel,
    generate_generic_pageable_response,
)
from backend.app.router import router
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.user_service import get_logged_user
from common.models.standard_form import StandardFormResponseDto
from common.models.user import User


@router(
    prefix="/workspaces/{workspace_id}",
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

    @get("/forms/{form_id}/submissions")
    async def _get_workspace_form_responses(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self._form_response_service.get_workspace_submissions(
            workspace_id, form_id, user
        )

    @get("/allSubmissions")
    async def _get_all_workspace_responses(
        self, workspace_id: PydanticObjectId, user=Depends(get_logged_user)
    ):
        data = await self._form_response_service.get_all_workspace_responses(
            workspace_id, user
        )
        return GenericResponseModel[List[StandardFormResponseDto]](
            payload=generate_generic_pageable_response(data)
        )

    @get("/submissions")
    async def _get_user_submissions_in_workspace(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        data = await self._form_response_service.get_user_submissions(
            workspace_id, user
        )
        return GenericResponseModel[List[StandardFormResponseDto]](
            payload=generate_generic_pageable_response(data)
        )

    # TODO : Insert form id here/ Make uniform endpoints
    @get("/submissions/{submission_id}")
    async def _get_workspace_form_response(
        self,
        workspace_id: PydanticObjectId,
        submission_id: str,
        user: User = Depends(get_logged_user),
    ):
        data = await self._form_response_service.get_workspace_submission(
            workspace_id, submission_id, user
        )
        return GenericResponseModel[StandardFormResponseDto](
            payload=generate_generic_pageable_response(data)
        )
