from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, post, get, delete
from common.models.user import User
from fastapi import Depends

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto, ActionResponse
from backend.app.router import router
from backend.app.services.actions_service import ActionService
from backend.app.services.user_service import get_logged_user, get_logged_admin


@router(
    prefix="",
    tags=["Actions"],
    responses={
        400: {"description": "Bad request"},
        401: {"message": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class ActionRouter(Routable):
    def __init__(
        self,
        actions_service: ActionService = container.action_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.action_service = actions_service

    # @post("/workspaces/{workspace_id}/actions", response_model=ActionResponse)
    # async def create_action(self, workspace_id: PydanticObjectId,
    #                         action: ActionDto, user: User = Depends(get_logged_user)):
    #     action = await self.action_service.create_action(workspace_id=workspace_id, action=action, user=user)
    #     return ActionResponse(**action.dict())

    @post("/actions")
    async def create_action(
        self, action: ActionDto, user: User = Depends(get_logged_admin)
    ):
        action = await self.action_service.create_global_action(
            action=action, user=user
        )
        return action

    @get(
        "/actions",
        response_model=List[ActionResponse],
    )
    async def get_all_actions(self, user: User = Depends(get_logged_user)):
        actions = await self.action_service.get_all_actions()
        return [ActionResponse(**action.dict()) for action in actions]

    @get("/actions/{action_id}", response_model=ActionResponse)
    async def get_action_by_id(
        self, action_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        action = await self.action_service.get_action_by_id(action_id=action_id)
        if not action:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Action not found")
        return ActionResponse(**action.dict())

    @delete("/actions/{action_id}")
    async def delete_action(
        self, action_id: PydanticObjectId, user: User = Depends(get_logged_admin)
    ):
        await self.action_service.delete_action_from_workspace(
            action_id=action_id,
        )
        return action_id
