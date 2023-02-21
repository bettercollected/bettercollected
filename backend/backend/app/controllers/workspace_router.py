from http import HTTPStatus
from typing import Optional

from beanie import PydanticObjectId
from fastapi import UploadFile, Form

from backend.app.container import container
from backend.app.models.workspace import WorkspaceResponseDto, WorkspaceRequestDto
from common.exceptions.http import HTTPException
from common.models.user import User
from common.utils.cbv import cbv
from common.utils.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/workspaces")


@cbv(router=router)
class WorkspaceRouter:
    def __int__(self):
        self._workspace_service = container.workspace_service()

    @router.get("/{workspace_id}")
    async def _get_workspace_by_id(self, workspace_id: PydanticObjectId):
        return await self._workspace_service.get_workspace_by_id(
            workspace_id=workspace_id
        )

    @router.get("/")
    async def _get_workspace_by_query(self, workspace_name: str, custom_domain: str):
        if workspace_name and custom_domain:
            raise HTTPException(HTTPStatus.CONFLICT, "Provide only one query")
        query = workspace_name if workspace_name else custom_domain
        return await self._workspace_service.get_workspace_by_query(query)

    @router.patch("/{workspace_id}")
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
        user: User = None,
    ) -> WorkspaceResponseDto:
        workspace_request = WorkspaceRequestDto(
            title=title,
            workspaceName=workspace_name,
            description=description,
            customDomain=custom_domain,
            ownerId=owner_id,
        )
        return await self._workspace_service.patch_workspace(
            profile_image, banner_image, workspace_id, workspace_request, user
        )

    @router.delete("/{workspace_id}/custom_domain")
    async def delete_custom_domain_of_workspace(
        self, workspace_id: PydanticObjectId, user: User = None
    ):
        return await self._workspace_service.delete_custom_domain_of_workspace(
            workspace_id=workspace_id, user=user
        )
