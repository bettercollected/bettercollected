from beanie import PydanticObjectId

from backend.app.models.dtos.workspace_responder_dto import WorkspaceResponderPatchDto
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.workspace_responders_repository import (
    WorkspaceRespondersRepository,
)
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission
from common.models.user import User


class WorkspaceRespondersService:
    def __init__(
        self,
        workspace_responders_repo: WorkspaceRespondersRepository,
        authorization_service: AuthorizationService,
        form_response_service: FormResponseService,
    ):
        self.workspace_responders_repo = workspace_responders_repo
        self.authorization_service = authorization_service
        self.form_response_service = form_response_service

    async def create_workspace_tag(
        self, workspace_id: PydanticObjectId, title: str, user: User
    ):
        await self.authorization_service.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )
        return await self.workspace_responders_repo.create_workspace_tag(
            workspace_id=workspace_id, title=title
        )

    async def get_workspace_tags(self, workspace_id: PydanticObjectId, user: User):
        await self.authorization_service.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
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
        await self.authorization_service.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )

        workspace_responder = await self.workspace_responders_repo.get_responder_by_email_and_workspace_id(
            workspace_id=workspace_id, email=email
        )
        if patch_request.metadata:
            workspace_responder.metadata = patch_request.metadata
        if patch_request.tags:
            workspace_responder.tags = patch_request.tags
        return await workspace_responder.save()
