from typing import List

from beanie import PydanticObjectId
from pydantic import EmailStr

from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.services.workspace_user_service import WorkspaceUserService
from common.models.user import User


class ResponderGroupsService:
    def __init__(
        self,
        responder_groups_repo: ResponderGroupsRepository,
        workspace_user_service: WorkspaceUserService,
    ):
        self.responder_groups_repo = responder_groups_repo
        self.workspace_user_service = workspace_user_service

    pass

    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        emails: List[EmailStr],
        user: User,
    ):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.responder_groups_repo.create_group(
            workspace_id=workspace_id, name=name, emails=emails
        )
