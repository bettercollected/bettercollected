from http import HTTPStatus
from typing import Optional, List

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, patch, delete
from fastapi import UploadFile, Form, Depends

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.generic_models import (
    GenericResponseModel,
    generate_generic_pageable_response,
)
from backend.app.models.workspace import WorkspaceResponseDto, WorkspaceRequestDto
from backend.app.router import router
from backend.app.services.user_service import get_logged_user
from backend.app.services.workspace_service import WorkspaceService
from common.models.user import User


@router(prefix="/workspaces", tags=["Workspaces"])
class WorkspaceRouter(Routable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace_service: WorkspaceService = container.workspace_service()

    @get("")
    async def _get_workspace_by_query(
        self, workspace_name: Optional[str] = None, custom_domain: Optional[str] = None
    ):
        if (workspace_name and custom_domain) or (
            not workspace_name and not custom_domain
        ):
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY, "Provide only one query"
            )
        query = workspace_name if workspace_name else custom_domain
        return await self.workspace_service.get_workspace_by_query(query)

    @get("/mine")
    async def _get_mine_workspaces(
        self, user: User = Depends(get_logged_user)
    ) -> GenericResponseModel[List[WorkspaceResponseDto]]:
        workspace = await self.workspace_service.get_mine_workspaces(user)
        return GenericResponseModel(
            payload=generate_generic_pageable_response(data=workspace)
        )

    @get("/{workspace_id}")
    async def _get_workspace_by_id(self, workspace_id: PydanticObjectId):
        return await self.workspace_service.get_workspace_by_id(
            workspace_id=workspace_id
        )

    @patch("/{workspace_id}")
    async def patch_workspace(
        self,
        workspace_id: PydanticObjectId,
        profile_image: UploadFile = None,
        banner_image: UploadFile = None,
        title: Optional[str] = Form(None),
        workspace_name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        custom_domain: Optional[str] = Form(None),
        owner_id: Optional[str] = Form(None),
        user: User = Depends(get_logged_user),
    ) -> WorkspaceResponseDto:
        workspace_request = WorkspaceRequestDto(
            title=title,
            workspace_name=workspace_name,
            description=description,
            custom_domain=custom_domain,
            owner_id=owner_id,
        )
        return await self.workspace_service.patch_workspace(
            profile_image, banner_image, workspace_id, workspace_request, user
        )

    @delete("/{workspace_id}/custom_domain")
    async def delete_custom_domain_of_workspace(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.workspace_service.delete_custom_domain_of_workspace(
            workspace_id=workspace_id, user=user
        )
