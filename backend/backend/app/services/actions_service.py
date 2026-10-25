from common.models.standard_form import Trigger
from loguru import logger
from common.models.user import User
from common.records import RecordId
from common.services.http_client import HttpClient
from starlette.requests import Request

from backend.app.models.dtos.action_dto import ActionDto, ActionResponse
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission


class ActionService:
    def __init__(
        self,
        action_repository: PostgresActionRepository,
        form_repo: FormRepository,
        temporal_service: TemporalService,
        http_client: HttpClient,
        form_provider_service: FormPluginProviderService,
        authorization_service: AuthorizationService,
        form_response_service: FormResponseService,
        workspace_repo=PostgresWorkspaceRepository,
        sheets_reconsent=None,
    ):
        self.action_repository = action_repository
        self.form_repo = form_repo
        self.temporal_service: TemporalService = temporal_service
        self.authorization_service = authorization_service
        self.http_client = http_client
        self.form_provider_service = form_provider_service
        self.form_response_service = form_response_service
        self.workspace_repo = workspace_repo
        # services/sheets_reconsent.py: holds back Sheets runs on a legacy grant
        self.sheets_reconsent = sheets_reconsent

    async def get_action(self, action_id: RecordId):
        return await self.action_repository.get_action_by_id(action_id)

    async def create_action(
        self, workspace_id: RecordId, action: ActionDto, user: User
    ):
        await self.authorization_service.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        created = await self.action_repository.create_action(
            workspace_id=workspace_id, action=action, user=user
        )
        return ActionResponse(**created.model_dump(mode="json"))

    async def get_all_actions(self):
        return await self.action_repository.get_all_actions()

    async def get_action_by_id(self, action_id: RecordId):
        return await self.action_repository.get_action_by_id(action_id=action_id)

    async def start_actions_for_submission(
        self,
        form: FormDocument,
        response: FormResponseDocument,
        workspace_id: RecordId,
    ):
        form_actions = form.actions
        if form_actions is None:
            return
        submission_actions = form.actions.get(Trigger.on_submit)
        submission_actions = [
            action.id for action in submission_actions if action.enabled
        ]
        if len(submission_actions) == 0:
            return
        actions = await self.action_repository.get_actions_by_ids(
            action_ids=submission_actions
        )
        skipped = 0
        for action in actions:
            if self.sheets_reconsent is not None and (
                await self.sheets_reconsent.hold_back_run(form, action, workspace_id)
            ):
                # a Google Sheets grant from before drive.file: never used again
                skipped += 1
                continue
            # if action.name == "integrate_google_sheets":
            #     google_sheet_id = [params.value for params in form.parameters.get(str(action.id)) if
            #                        params.name == "Google Sheet Id"]
            #     provider_url = await self.form_provider_service.get_provider_url(FormProvider.GOOGLE)
            #     read_google_sheet_url = f"{provider_url}/{FormProvider.GOOGLE}/forms/read_google_sheet"
            #     response = await self.http_client.get(read_google_sheet_url,
            #                                           params={'google_sheet_id': google_sheet_id[0]},
            #                                           cookies=request.cookies)
            #     print(response)
            workspace = await self.workspace_repo.get_workspace_with_action_by_id(
                workspace_id=workspace_id, action_id=action.id
            )
            await self.temporal_service.start_action_execution(
                action=action, form=form, response=response, workspace=workspace
            )
        if skipped:
            logger.info(
                "actions skipped for re-consent: form={} workspace={} count={}",
                form.form_id,
                workspace_id,
                skipped,
            )

    async def delete_action_from_workspace(self, action_id: RecordId):
        await self.form_repo.remove_action_from_all_forms(action_id=action_id)
        await self.action_repository.delete_action(action_id=action_id)

    async def create_action_in_workspace_from_action(
        self, workspace_id: RecordId, action: ActionResponse, user: User
    ):
        action = await self.action_repository.get_action_by_id(action.id)
        return await self.action_repository.create_action_in_workspace_from_action(
            workspace_id=workspace_id, action_id=action.id
        )

    async def create_global_action(self, action: ActionDto, user: User):
        return await self.action_repository.create_global_action(
            action=action, user=user
        )
