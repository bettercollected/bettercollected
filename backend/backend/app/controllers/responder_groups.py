from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, post
from fastapi import Depends
from pydantic import EmailStr

from backend.app.container import container
from backend.app.router import router
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.user_service import get_logged_user
from common.models.user import User


@router(prefix="/{workspace_id}/responder-groups", tags=["Responders Group"])
class ResponderGroupsRouter(Routable):
    def __init__(
        self,
        responder_groups_service: ResponderGroupsService = container.responder_groups_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.responder_groups_service = responder_groups_service

    @post("")
    async def create(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        emails: List[EmailStr] = None,
        user: User = Depends(get_logged_user),
    ):
        return await self.responder_groups_service.create_group(
            workspace_id, name, emails, user
        )
