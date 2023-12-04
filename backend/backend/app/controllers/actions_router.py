from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, post, get
from common.models.user import User
from fastapi import Depends

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto, ActionResponse
from backend.app.router import router
from backend.app.services.actions_service import ActionService
from backend.app.services.user_service import get_logged_admin


@router(
    prefix="/actions",
    tags=["Actions"],
    responses={
        400: {"description": "Bad request"},
        401: {"message": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    }
)
class ActionRouter(Routable):

    def __init__(self, actions_service: ActionService = container.action_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_service = actions_service

    @post("", response_model=ActionResponse)
    async def create_action(self,
                            action: ActionDto, user: User = Depends(get_logged_admin)):
        return await self.action_service.create_action(action=action, user=user)

    @get("", response_model=List[ActionResponse])
    async def get_all_actions(self, user: User = Depends(get_logged_admin)):
        actions = await self.action_service.get_all_actions()
        return [ActionResponse(**action.dict()) for action in actions]

    @get("/{action_id}", response_model=ActionResponse)
    async def get_action_by_id(self, action_id: PydanticObjectId, user: User = Depends(get_logged_admin)):
        action = await self.action_service.get_action_by_id(action_id)
        return ActionResponse(**action.dict())
