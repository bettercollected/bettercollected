from http import HTTPStatus

from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.repositories.action_repository import ActionRepository


class ActionService:
    def __init__(self, action_repository: ActionRepository):
        self.action_repository = action_repository

    async def create_action(self, action: ActionDto, user: User):
        if not user.is_admin():
            raise HTTPException(HTTPStatus.FORBIDDEN, MESSAGE_FORBIDDEN)
        return await self.action_repository.create_action(name=action.name, action_code=action.action_code,
                                                          parameters=action.parameters,
                                                          user=user)
