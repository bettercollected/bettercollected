from typing import Any

from beanie import PydanticObjectId
from classy_fastapi import Routable, post, get, patch
from fastapi import Depends
from fastapi_pagination import Page
from pydantic import EmailStr

from backend.app.container import container
from backend.app.models.dtos.workspace_tag_dto import WorkspaceTagRequest
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.router import router
from backend.app.services.user_service import get_logged_user
from backend.app.services.workspace_responders_service import WorkspaceRespondersService
from common.models.user import User


@router(prefix="/{workspace_id}/responders", tags=["Workspace Responders"])
class WorkspaceRespondersController(Routable):
    def __init__(
        self,
        workspace_responders_service: WorkspaceRespondersService = container.workspace_responders_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.workspace_responders_service = workspace_responders_service

    @get("", response_model=Page[Any])
    async def get_workspace_responders(
        self,
        workspace_id: PydanticObjectId,
        filter_query: FormResponseFilterQuery = Depends(None),
        sort: SortRequest = Depends(None),
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_responders_service.get_workspace_responders(
            workspace_id=workspace_id, filter_query=filter_query, sort=sort, user=user
        )
        pass

    @get("/tags")
    async def get_all_workspace_tags(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.workspace_responders_service.get_workspace_tags(
            workspace_id, user
        )

    @post("/tags")
    async def create_workspace_tag(
        self,
        workspace_id: PydanticObjectId,
        create_request: WorkspaceTagRequest,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_responders_service.create_workspace_tag(
            workspace_id=workspace_id, title=create_request.title, user=user
        )

    @patch("")
    async def patch_workspace_responder_with_email(self, email: EmailStr):
        pass
