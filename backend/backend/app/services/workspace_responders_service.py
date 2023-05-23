from beanie import PydanticObjectId

from backend.app.models.dtos.workspace_responder_dto import WorkspaceResponderPatchDto
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.workspace_responders_repository import (
    WorkspaceRespondersRepository,
)
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.workspace_user_service import WorkspaceUserService
from common.models.user import User


class WorkspaceRespondersService:
    def __init__(
        self,
        workspace_responders_repo: WorkspaceRespondersRepository,
        workspace_user_service: WorkspaceUserService,
        form_response_service: FormResponseService,
    ):
        self.workspace_responders_repo = workspace_responders_repo
        self.workspace_user_service = workspace_user_service
        self.form_response_service = form_response_service

    async def create_workspace_tag(
        self, workspace_id: PydanticObjectId, title: str, user: User
    ):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.workspace_responders_repo.create_workspace_tag(
            workspace_id=workspace_id, title=title
        )

    async def get_workspace_tags(self, workspace_id: PydanticObjectId, user: User):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.workspace_responders_repo.get_workspace_tags(
            workspace_id=workspace_id
        )

    async def get_workspace_responders(
        self,
        workspace_id: PydanticObjectId,
        filter_query: FormResponseFilterQuery,
        sort: SortRequest,
        user: User,
    ):
        return await self.form_response_service.get_all_workspace_responses(
            workspace_id=workspace_id,
            filter_query=filter_query,
            sort=sort,
            request_for_deletion=False,
            data_subjects=True,
            user=user,
        )

    async def patch_workspace_responder_with_email(
        self,
        workspace_id: PydanticObjectId,
        email: str,
        patch_request: WorkspaceResponderPatchDto,
        user: User,
    ):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )

        workspace_responder = await self.workspace_responders_repo.get_responder_by_email_and_workspace_id(
            workspace_id=workspace_id, email=email
        )
        if patch_request.metadata:
            workspace_responder.metadata = patch_request.metadata
        if patch_request.tags:
            workspace_responder.tags = patch_request.tags
        return await workspace_responder.save()
