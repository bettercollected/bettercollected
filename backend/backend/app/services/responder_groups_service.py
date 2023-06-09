from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId
from pydantic import EmailStr

from backend.app.constants.messages import not_found
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.services.form_service import FormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from common.models.user import User


class ResponderGroupsService:
    def __init__(
        self,
        responder_groups_repo: ResponderGroupsRepository,
        workspace_user_service: WorkspaceUserService,
        form_service: FormService,
    ):
        self.responder_groups_repo = responder_groups_repo
        self.workspace_user_service = workspace_user_service
        self.form_service = form_service

    async def get_users_in_group(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(workspace_id, user)
        response = await self.responder_groups_repo.get_emails_in_group(
            group_id=group_id
        )
        forms = []
        for form_id in response["forms"]:
            forms.append(
                await self.form_service.get_form_by_id(workspace_id, form_id, user)
            )
        response["forms"] = forms
        if not response:
            return HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Group not found."
            )
        return ResponderGroupDto(**response)

    async def update_responder_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        user: User,
        name: str,
        emails: List[EmailStr],
        description: str,
    ):
        await self.check_user_can_access_group(
            workspace_id=workspace_id, group_id=group_id, user=user
        )
        response = await self.responder_groups_repo.update_group(
            group_id=group_id,
            emails=emails,
            name=name,
            description=description,
            workspace_id=workspace_id,
        )
        return response.dict()

    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        emails: List[EmailStr],
        user: User,
        description: str,
    ):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.responder_groups_repo.create_group(
            workspace_id=workspace_id, name=name, emails=emails, description=description
        )

    async def add_emails_to_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        emails: List[EmailStr],
        user: User,
    ):
        await self.check_user_can_access_group(
            workspace_id=workspace_id, group_id=group_id, user=user
        )
        await self.responder_groups_repo.add_emails_to_group(
            group_id=group_id, emails=emails
        )

    async def remove_emails_from_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        emails: List[EmailStr],
        user: User,
    ):
        await self.check_user_can_access_group(
            workspace_id=workspace_id, group_id=group_id, user=user
        )
        await self.responder_groups_repo.remove_emails_from_group(
            group_id=group_id, emails=emails
        )

    async def check_user_can_access_group(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId, user: User
    ):
        await self.workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        group = await self.responder_groups_repo.get_group_in_workspace(
            workspace_id=workspace_id, group_id=group_id
        )
        if not group:
            return HTTPException(status_code=HTTPStatus.NOT_FOUND, content=not_found)

    async def remove_responder_group(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId, user: User
    ):
        await self.check_user_can_access_group(
            workspace_id=workspace_id, user=user, group_id=group_id
        )
        await self.responder_groups_repo.remove_responder_group(group_id=group_id)

    async def get_groups_in_workspace(self, workspace_id: PydanticObjectId, user: User):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        groups = await self.responder_groups_repo.get_groups_in_workspace(
            workspace_id=workspace_id
        )

        for group in groups:
            forms = []
            for form_id in group.forms:
                forms.append(
                    await self.form_service.get_form_by_id(workspace_id, form_id, user)
                )
            group.forms = forms
        return groups

    async def add_group_to_form(self, form_id: str, group_id: PydanticObjectId):
        return await self.responder_groups_repo.add_group_to_form(
            form_id=form_id, group_id=group_id
        )

    async def remove_group_from_form(self, form_id: str, group_id: PydanticObjectId):
        await self.responder_groups_repo.remove_group_from_form(
            form_id=form_id, group_id=group_id
        )
