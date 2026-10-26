from http import HTTPStatus
from typing import List

from common.ids import RecordId

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.workspace_responder_dto import WorkspaceResponderPatchDto
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.postgres.responses import (
    PostgresWorkspaceRespondersRepository,
)
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission
from common.constants import MESSAGE_NOT_FOUND
from common.models.user import User


class WorkspaceRespondersService:
    def __init__(
        self,
        workspace_responders_repo: PostgresWorkspaceRespondersRepository,
        authorization_service: AuthorizationService,
        form_response_service: FormResponseService,
    ):
        self.workspace_responders_repo = workspace_responders_repo
        self.authorization_service = authorization_service
        self.form_response_service = form_response_service

    async def create_workspace_tag(
        self, workspace_id: RecordId, title: str, user: User
    ):
        await self.authorization_service.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )
        return await self.workspace_responders_repo.create_workspace_tag(
            workspace_id=workspace_id, title=title
        )

    async def get_workspace_tags(self, workspace_id: RecordId, user: User):
        await self.authorization_service.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )
        return await self.workspace_responders_repo.get_workspace_tags(
            workspace_id=workspace_id
        )

    async def get_workspace_responders(
        self,
        workspace_id: RecordId,
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
        workspace_id: RecordId,
        email: str,
        patch_request: WorkspaceResponderPatchDto,
        user: User,
    ):
        await self.authorization_service.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )

        if patch_request.tags:
            await self._require_workspace_tags(workspace_id, patch_request.tags)

        return await self.workspace_responders_repo.patch_responder(
            workspace_id=workspace_id,
            email=email,
            metadata=patch_request.metadata,
            tags=patch_request.tags,
        )

    async def _require_workspace_tags(
        self, workspace_id: RecordId, tag_ids: List[RecordId]
    ):
        """404 unless every tag belongs to this workspace. A tag of another
        workspace answers exactly like one that does not exist."""
        own = {
            str(tag.id)
            for tag in await self.workspace_responders_repo.get_workspace_tags(
                workspace_id=workspace_id
            )
        }
        if any(str(tag_id) not in own for tag_id in tag_ids):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
