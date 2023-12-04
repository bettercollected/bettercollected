from http import HTTPStatus

from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import Trigger
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.repositories.action_repository import ActionRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.temporal_service import TemporalService


class ActionService:
    def __init__(self, action_repository: ActionRepository, temporal_service: TemporalService):
        self.action_repository = action_repository
        self.temporal_service: TemporalService = temporal_service

    async def create_action(self, action: ActionDto, user: User):
        if not user.is_admin():
            raise HTTPException(HTTPStatus.FORBIDDEN, MESSAGE_FORBIDDEN)
        return await self.action_repository.create_action(name=action.name, action_code=action.action_code,
                                                          parameters=action.parameters,
                                                          user=user)

    async def get_all_actions(self):
        return await self.action_repository.get_all_actions()

    async def get_action_by_id(self, action_id: PydanticObjectId):
        return await self.action_repository.get_action_by_id(action_id)

    async def start_actions_for_submission(self, form: FormDocument, response: FormResponseDocument):
        submission_actions = form.actions.get(Trigger.on_submit)
        if submission_actions is None:
            return
        actions = await self.action_repository.get_actions_by_ids(submission_actions)
        for action in actions:
            await self.temporal_service.start_action_execution(action=action, form=form, response=response)
