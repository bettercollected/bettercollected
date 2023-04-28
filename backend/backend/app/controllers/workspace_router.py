from http import HTTPStatus
from typing import List, Optional

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.workspace import (
    WorkspaceRequestDtoCamel,
    WorkspaceResponseDto,
)
from backend.app.router import router
from backend.app.services.user_service import get_logged_user, get_user_if_logged_in
from backend.app.services.workspace_service import WorkspaceService

from beanie import PydanticObjectId

from classy_fastapi import Routable, delete, get, patch, post

from common.models.user import User

from fastapi import Depends, Form, UploadFile

from pydantic import EmailStr


@router(prefix="/workspaces", tags=["Workspaces"])
class WorkspaceRouter(Routable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace_service: WorkspaceService = container.workspace_service()

    @get("")
    async def _get_workspace_by_query(
        self,
        workspace_name: Optional[str] = None,
        custom_domain: Optional[str] = None,
        user: User = Depends(get_user_if_logged_in),
    ):
        if (workspace_name and custom_domain) or (
            not workspace_name and not custom_domain
        ):
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY, "Provide only one query"
            )
        query = workspace_name if workspace_name else custom_domain
        return await self.workspace_service.get_workspace_by_query(query, user)

    @get("/mine")
    async def _get_mine_workspaces(
        self, user: User = Depends(get_logged_user)
    ) -> List[WorkspaceResponseDto]:
        workspaces = await self.workspace_service.get_mine_workspaces(user)
        return workspaces

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
        workspace_request = WorkspaceRequestDtoCamel(
            title=title,
            workspace_name=workspace_name,
            description=description,
            custom_domain=custom_domain,
            owner_id=owner_id,
        )
        return await self.workspace_service.patch_workspace(
            profile_image, banner_image, workspace_id, workspace_request, user
        )

    @post("/{workspace_id}/auth/otp/send")
    async def send_otp_for_workspace(
        self,
        workspace_id: PydanticObjectId,
        receiver_email: EmailStr,
    ):
        return await self.workspace_service.send_otp_for_workspace(
            workspace_id, receiver_email
        )

    @delete("/{workspace_id}/custom_domain")
    async def delete_custom_domain_of_workspace(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.workspace_service.delete_custom_domain_of_workspace(
            workspace_id=workspace_id, user=user
        )

    @get("/{workspace_id}/stats")
    async def get_workspace_stats(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.workspace_service.get_workspace_stats(workspace_id, user)
