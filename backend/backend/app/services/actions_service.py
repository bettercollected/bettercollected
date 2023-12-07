from beanie import PydanticObjectId
from common.models.standard_form import Trigger
from common.models.user import User

from backend.app.models.dtos.action_dto import ActionDto
from backend.app.repositories.action_repository import ActionRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.temporal_service import TemporalService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings


class ActionService:
    def __init__(self, action_repository: ActionRepository, temporal_service: TemporalService,
                 workspace_user_service: WorkspaceUserService):
        self.action_repository = action_repository
        self.temporal_service: TemporalService = temporal_service
        self.workspace_user_service = workspace_user_service

    async def create_action(self, workspace_id: PydanticObjectId, action: ActionDto, user: User):
        await self.workspace_user_service.check_is_admin_in_workspace(workspace_id=workspace_id, user=user)
        return await self.action_repository.create_action(workspace_id=workspace_id, action=action,
                                                          user=user)

    async def get_all_actions(self, workspace_id: PydanticObjectId, user: User):
        if not workspace_id:
            workspace_id = settings.default_workspace_settings.WORKSPACE_ID
        else:
            await self.workspace_user_service.check_user_has_access_in_workspace(workspace_id=workspace_id, user=user)
        return await self.action_repository.get_all_actions(workspace_id=workspace_id, public_only=not workspace_id)

    async def get_action_by_id(self, workspace_id: PydanticObjectId, action_id: PydanticObjectId, user: User):
        if not workspace_id:
            workspace_id = settings.default_workspace_settings.WORKSPACE_ID
        else:
            await self.workspace_user_service.check_user_has_access_in_workspace(workspace_id=workspace_id, user=user)

        return await self.action_repository.get_action_by_id(workspace_id=workspace_id, action_id=action_id)

    async def start_actions_for_submission(self, workspace_id: PydanticObjectId, form: FormDocument,
                                           response: FormResponseDocument):
        submission_actions = form.actions.get(Trigger.on_submit)
        if submission_actions is None:
            return
        actions = await self.action_repository.get_actions_by_ids(workspace_id=workspace_id,
                                                                  action_ids=submission_actions)
        for action in actions:
            await self.temporal_service.start_action_execution(action=action, form=form, response=response)
