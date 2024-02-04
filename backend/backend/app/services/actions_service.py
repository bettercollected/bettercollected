from beanie import PydanticObjectId
from common.enums.form_provider import FormProvider
from common.models.standard_form import Trigger
from common.models.user import User
from common.services.http_client import HttpClient

from backend.app.models.dtos.action_dto import ActionDto, ActionResponse
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.workspace_user_service import WorkspaceUserService


class ActionService:
    def __init__(self, action_repository: ActionRepository, temporal_service: TemporalService,
                 http_client: HttpClient, form_provider_service: FormPluginProviderService,
                 workspace_user_service: WorkspaceUserService,
                 form_response_service: FormResponseService,
                 workspace_repo=WorkspaceRepository
                 ):
        self.action_repository = action_repository
        self.temporal_service: TemporalService = temporal_service
        self.workspace_user_service = workspace_user_service
        self.http_client = http_client
        self.form_provider_service = form_provider_service
        self.form_response_service = form_response_service
        self.workspace_repo = workspace_repo

    async def get_action(self, action_id: PydanticObjectId):
        return await self.action_repository.get_action_by_id(action_id)

    async def create_action(self, workspace_id: PydanticObjectId, action: ActionDto, user: User):
        await self.workspace_user_service.check_is_admin_in_workspace(workspace_id=workspace_id, user=user)
        return await self.action_repository.create_action(workspace_id=workspace_id, action=action,
                                                          user=user)

    async def get_all_actions(self):
        return await self.action_repository.get_all_actions()

    async def get_action_by_id(self, action_id: PydanticObjectId):
        return await self.action_repository.get_action_by_id(action_id=action_id)

    async def start_actions_for_submission(self, form: FormDocument,
                                           response: FormResponseDocument, workspace_id: PydanticObjectId,
                                           ):
        form_actions = form.actions
        if form_actions is None:
            return
        submission_actions = form.actions.get(Trigger.on_submit)
        submission_actions = [action.id for action in submission_actions if action.enabled]
        if len(submission_actions) == 0:
            return
        actions = await self.action_repository.get_actions_by_ids(action_ids=submission_actions)
        for action in actions:
            workspace = await self.workspace_repo.get_workspace_with_action_by_id(workspace_id=workspace_id,
                                                                                  action_id=action.id)
            await self.temporal_service.start_action_execution(action=action, form=form, response=response,
                                                               workspace=workspace)

    async def delete_action_from_workspace(self, action_id: PydanticObjectId):
        await self.action_repository.remove_action_form_all_forms(action_id=action_id)
        await self.action_repository.delete_action(action_id=action_id)

    async def create_action_in_workspace_from_action(self, workspace_id: PydanticObjectId, action: ActionResponse,
                                                     user: User):
        action = await self.action_repository.get_action_by_id(action.id)
        if action is not None and action.name == 'integrate_google_sheets':
            provider_url = await self.form_provider_service.get_provider_url(FormProvider.GOOGLE)
            fetch_credential_url = f"{provider_url}/{FormProvider.GOOGLE}/credentials"
            credentials = await self.http_client.get(fetch_credential_url, params={'email': user.sub})
            return await self.action_repository.create_action_in_workspace_from_action(workspace_id=workspace_id,
                                                                                       action_id=action.id,
                                                                                       credentials=credentials)
        else:
            return await self.action_repository.create_action_in_workspace_from_action(workspace_id=workspace_id,
                                                                                       action_id=action.id)

    async def create_global_action(self, action: ActionDto, user: User):
        return await self.action_repository.create_global_action(action=action, user=user)
