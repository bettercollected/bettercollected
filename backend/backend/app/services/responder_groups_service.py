import re
from http import HTTPStatus
from typing import Dict, List, Optional

from common.ids import RecordId
from pydantic import EmailStr

from backend.app.constants.messages import not_found
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.repositories.postgres.responses import (
    PostgresResponderGroupsRepository,
)
from backend.app.services.form_service import FormService
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission
from common.models.user import User


def validate_group_regex(regex: Optional[str]) -> None:
    """A responder group's regex must compile: it is evaluated against every
    responder's identifier when private forms are listed."""
    if not regex:
        return
    try:
        re.compile(regex)
    except re.error as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            content=f"Invalid regex: {error}",
        )


def _oid(value) -> RecordId:
    return RecordId(str(value))


def _other_workspaces(workspace_id, form_workspace_ids) -> set:
    """The other workspaces that hold the form."""
    return {_oid(other) for other in form_workspace_ids} - {_oid(workspace_id)}


class ResponderGroupsService:
    def __init__(
        self,
        responder_groups_repo: PostgresResponderGroupsRepository,
        authorization_service: AuthorizationService,
        form_service: FormService,
    ):
        self.responder_groups_repo = responder_groups_repo
        self.authorization_service = authorization_service
        self.form_service = form_service

    async def get_users_in_group(
        self, workspace_id: RecordId, group_id: RecordId, user: User
    ):
        await self.authorization_service.authorize(
            user, Permission.FORM_EDIT, workspace_id
        )
        if not await self.responder_groups_repo.get_group_in_workspace(
            workspace_id=workspace_id, group_id=group_id
        ):
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=not_found)
        response = await self.responder_groups_repo.get_emails_in_group(
            group_id=group_id
        )
        response["forms"] = await self._forms_in_workspace(
            workspace_id, response["forms"], user
        )
        if not response:
            return HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Group not found."
            )
        return ResponderGroupDto(**response)

    async def update_responder_group(
        self,
        workspace_id: RecordId,
        group_id: RecordId,
        user: User,
        name: str,
        emails: List[EmailStr],
        regex: str,
        description: str,
    ):
        await self.check_user_can_access_group(
            workspace_id=workspace_id, group_id=group_id, user=user
        )
        validate_group_regex(regex)
        response = await self.responder_groups_repo.update_group(
            group_id=group_id,
            emails=emails,
            name=name,
            description=description,
            workspace_id=workspace_id,
            regex=regex,
        )
        return response.model_dump(mode="json")

    async def create_group(
        self,
        workspace_id: RecordId,
        name: str,
        emails: List[EmailStr],
        user: User,
        form_id: str,
        description: str,
        regex: str,
    ):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        validate_group_regex(regex)
        if form_id:
            await self.form_service.check_form_in_workspace(workspace_id, form_id)
        group = await self.responder_groups_repo.create_group(
            workspace_id=workspace_id, name=name, description=description, regex=regex
        )
        if isinstance(group, dict):  # validation message from the repository
            return group
        if emails:
            await self.responder_groups_repo.add_emails_to_group(
                group_id=group.id, emails=emails
            )
        if form_id:
            await self.responder_groups_repo.add_group_to_form(
                form_id=form_id, group_id=group.id
            )
        return group

    async def add_emails_to_group(
        self,
        workspace_id: RecordId,
        group_id: RecordId,
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
        workspace_id: RecordId,
        group_id: RecordId,
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
        self, workspace_id: RecordId, group_id: RecordId, user: User
    ):
        await self.authorization_service.authorize(
            user, Permission.MEMBERS_MANAGE, workspace_id
        )
        group = await self.responder_groups_repo.get_group_in_workspace(
            workspace_id=workspace_id, group_id=group_id
        )
        if not group:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=not_found)

    async def remove_responder_group(
        self, workspace_id: RecordId, group_id: RecordId, user: User
    ):
        await self.check_user_can_access_group(
            workspace_id=workspace_id, user=user, group_id=group_id
        )
        await self.responder_groups_repo.remove_responder_group(group_id=group_id)

    async def get_groups_in_workspace(self, workspace_id: RecordId, user: User):
        await self.authorization_service.authorize(
            user, Permission.FORM_EDIT, workspace_id
        )
        groups = await self.responder_groups_repo.get_groups_in_workspace(
            workspace_id=workspace_id
        )

        for group in groups:
            group.forms = await self._forms_in_workspace(
                workspace_id, group.forms, user
            )
        return groups

    async def _forms_in_workspace(
        self, workspace_id: RecordId, form_ids: List[str], user: User
    ) -> list:
        """The group's forms that are in the workspace. A link to a form of
        another workspace (made before links were checked) is skipped rather
        than failing the whole listing."""
        forms = []
        for form_id in form_ids:
            try:
                forms.append(
                    await self.form_service.get_form_by_id(
                        workspace_id, form_id, user=user
                    )
                )
            except HTTPException as error:
                if error.status_code != HTTPStatus.NOT_FOUND:
                    raise
        return forms

    async def check_groups_in_workspace(
        self, workspace_id: RecordId, group_ids: List[RecordId]
    ) -> None:
        """404, as for an unknown group, unless every id is a responder group
        of the workspace."""
        for group_id in dict.fromkeys(group_ids):
            if not await self.responder_groups_repo.get_group_in_workspace(
                workspace_id=workspace_id, group_id=group_id
            ):
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=not_found)

    async def _linked_group_owners(
        self, form_id: str
    ) -> Dict[RecordId, Optional[RecordId]]:
        """group id -> the workspace that owns it, for the form's groups."""
        groups = await self.responder_groups_repo.get_groups_by_form_ids([form_id])
        return {
            _oid(group["_id"]): (
                _oid(group["workspace_id"]) if group.get("workspace_id") else None
            )
            for group in groups.get(form_id, [])
        }

    async def add_groups_to_form(
        self,
        workspace_id: RecordId,
        form_id: str,
        group_ids: List[RecordId],
        form_workspace_ids: List[RecordId],
    ):
        """Set the workspace's groups on one of its forms (the whole set the
        builder sends, which lists every group linked to the form, whatever
        its workspace). An id not linked to the form must be a group of the
        workspace: otherwise 404, as for an unknown group, and nothing is
        linked or unlinked. An id of another workspace's group already linked
        to the form reveals nothing new and is not refused: the groups of
        another workspace that holds the form stay linked whether or not they
        are sent, and a link to a group of a workspace that doesn't hold the
        form (made before links were checked) is dropped."""
        owners = await self._linked_group_owners(form_id)
        own_id = _oid(workspace_id)
        own, unlinked = [], []
        for group_id in dict.fromkeys(_oid(g) for g in group_ids):
            if group_id not in owners:
                unlinked.append(group_id)
            elif owners[group_id] == own_id:
                own.append(group_id)
        await self.check_groups_in_workspace(workspace_id, unlinked)
        other_workspaces = _other_workspaces(workspace_id, form_workspace_ids)
        kept = [
            group_id
            for group_id, owner in owners.items()
            if owner is not None and owner in other_workspaces
        ]
        return await self.responder_groups_repo.add_groups_to_form(
            form_id, own + unlinked + kept
        )

    async def remove_group_from_form(
        self,
        workspace_id: RecordId,
        form_id: str,
        group_id: RecordId,
        form_workspace_ids: List[RecordId],
    ):
        """Unlink one of the workspace's groups from one of its forms. A link
        to another workspace's group may be removed only when that workspace
        doesn't hold the form (a link made before links were checked); 404
        otherwise, as for an unknown group."""
        if not await self.responder_groups_repo.get_group_in_workspace(
            workspace_id=workspace_id, group_id=group_id
        ):
            owners = await self._linked_group_owners(form_id)
            other_workspaces = _other_workspaces(workspace_id, form_workspace_ids)
            if group_id not in owners or owners[group_id] in other_workspaces:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=not_found)
        await self.responder_groups_repo.remove_group_from_form(
            form_id=form_id, group_id=group_id
        )

    async def delete_groups_of_workspaces(self, workspace_ids: List[RecordId]):
        await self.responder_groups_repo.delete_responder_groups(
            workspace_ids=workspace_ids
        )
