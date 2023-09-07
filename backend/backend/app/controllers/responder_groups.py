from typing import List, Optional

from beanie import PydanticObjectId
from classy_fastapi import Routable, post, patch, get, delete
from fastapi import Depends
from pydantic import EmailStr

from backend.app.container import container
from backend.app.decorators.user_tag_decorators import user_tag
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.router import router
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.user_service import get_logged_user
from common.models.user import User


@router(
    prefix="/{workspace_id}/responder-groups",
    tags=["Responders Group"],
    responses={
        400: {"description": "Bad request"},
    },
)
class ResponderGroupsRouter(Routable):
    def __init__(
        self,
        responder_groups_service: ResponderGroupsService = container.responder_groups_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.responder_groups_service = responder_groups_service

    @get(
        "",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def get_groups_in_workspace(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.responder_groups_service.get_groups_in_workspace(
            workspace_id=workspace_id, user=user
        )

    @post(
        "",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    @user_tag(tag=UserTagType.GROUP_CREATED)
    async def create(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        form_id: Optional[str] = None,
        regex: Optional[str] = None,
        user: User = Depends(get_logged_user),
    ):
        return await self.responder_groups_service.create_group(
            workspace_id, name, emails, user, form_id, description, regex
        )

    @get(
        "/{group_id}",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def get_user_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.responder_groups_service.get_users_in_group(
            workspace_id=workspace_id, group_id=group_id, user=user
        )

    @patch(
        "/{group_id}",
        summary="Update Responder Group",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def update_user_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        regex: Optional[str] = None,
        user: User = Depends(get_logged_user),
    ):
        return await self.responder_groups_service.update_responder_group(
            workspace_id=workspace_id,
            name=name,
            group_id=group_id,
            description=description,
            emails=emails,
            user=user,
            regex=regex,
        )

    @patch(
        "/{group_id}/emails",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def add_emails_to_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        emails: List[EmailStr],
        user: User = Depends(get_logged_user),
    ):
        return await self.responder_groups_service.add_emails_to_group(
            workspace_id=workspace_id, group_id=group_id, emails=emails, user=user
        )

    @delete(
        "/{group_id}/emails",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def delete_emails_from_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        emails: List[EmailStr],
        user: User = Depends(get_logged_user),
    ):
        await self.responder_groups_service.remove_emails_from_group(
            workspace_id=workspace_id, group_id=group_id, emails=emails, user=user
        )
        return "Removed emails"

    @delete(
        "/{group_id}",
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def delete_responder_group(
        self,
        workspace_id: PydanticObjectId,
        group_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        await self.responder_groups_service.remove_responder_group(
            workspace_id=workspace_id, group_id=group_id, user=user
        )
        return "Group Deleted"
