from classy_fastapi import Routable, post
from common.models.user import User
from fastapi import Depends

from backend.app.models.dtos.action_dto import ActionDto
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
    },
)
class ActionRouter(Routable):

    def __init__(self, actions_service: ActionService, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.action_service = actions_service

    @post("")
    async def create_action(self,
                            action: ActionDto, user: User = Depends(get_logged_admin)):
        return await self.action_service.create_action(action=action, user=user)
