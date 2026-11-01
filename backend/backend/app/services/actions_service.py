import asyncio
from typing import Optional

from common.models.standard_form import Trigger
from cryptography.fernet import InvalidToken
from http import HTTPStatus
from loguru import logger
from common.models.user import User
from common.records import RecordId
from common.services.http_client import HttpClient
from starlette.requests import Request

from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
)
from backend.app.models.dtos.action_dto import ActionDto, ActionResponse
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.internal_fields import strip_internal_fields
from backend.jobs import signals
from backend.app.exceptions import HTTPException as AppHTTPException
from backend.app.models.workspace import WorkspaceRequestWithActionDto
from backend.app.models.enum.permission import Permission
from backend.app.services.copy_recipient import (
    CREATOR_COPY_ACTION,
    not_allowed,
    recipient_values,
)


QUEUE_ATTEMPTS = 3
QUEUE_RETRY_SECONDS = 0.3


def _only(settings_by_action, action_id):
    """``settings_by_action`` (a dict keyed by action id, or None) with only
    ``action_id``'s entry."""
    if not settings_by_action:
        return settings_by_action
    return {k: v for k, v in settings_by_action.items() if str(k) == str(action_id)}


class ActionService:
    def __init__(
        self,
        action_repository: PostgresActionRepository,
        form_repo: PostgresFormRepository,
        temporal_service: TemporalService,
        http_client: HttpClient,
        form_provider_service: FormPluginProviderService,
        authorization_service: AuthorizationService,
        form_response_service: FormResponseService,
        workspace_repo=PostgresWorkspaceRepository,
        sheets_reconsent=None,
        crypto=None,
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
        # the Fernet key ring that seals the stored secrets: opens them for an
        # executor that asks (``action_run_context(plain_secrets=True)``)
        self.crypto = crypto

    def _opened(self, values, action_id):
        """``values`` (secrets, each sealed) with every value opened, or None.
        A value no key of the ring opens fails the run's context (500), logged
        by ids: the run is not started on a secret that is silently missing."""
        if values is None:
            return None
        opened = []
        for item in values:
            if item.value in (None, ""):
                opened.append(item)
                continue
            try:
                opened.append(
                    item.model_copy(update={"value": self.crypto.decrypt(item.value)})
                )
            except (InvalidToken, TypeError, ValueError):
                logger.error(
                    "a stored secret of action {} cannot be opened with this "
                    "deployment's key (name {})",
                    action_id,
                    item.name,
                )
                raise AppHTTPException(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "A stored secret could not be opened.",
                )
        return opened

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
            await self._queue_run(action, form, response, workspace)
        if skipped:
            logger.info(
                "actions skipped for re-consent: form={} workspace={} count={}",
                form.form_id,
                workspace_id,
                skipped,
            )

    async def _queue_run(self, action, form, response, workspace) -> None:
        """Queue one run; a transient failure is tried again (the pool of
        queue connections can be busy). A run that still cannot be queued does
        not fail the submission, which is stored, nor keep the form's other
        actions from running: it is counted and logged as an error with a fixed
        event name and ids (``action_run_not_queued``), and no run happens (it
        is not queued later)."""
        for attempt in range(QUEUE_ATTEMPTS):
            try:
                await self.temporal_service.start_action_execution(
                    action=action, form=form, response=response, workspace=workspace
                )
                return
            except Exception as exc:  # noqa: BLE001 - ids and the class only
                if attempt + 1 < QUEUE_ATTEMPTS:
                    await asyncio.sleep(QUEUE_RETRY_SECONDS * (attempt + 1))
                    continue
                signals.action_run_not_queued()
                logger.error(
                    "action_run_not_queued: action={} form={} response={} ({})",
                    action.id,
                    form.form_id,
                    response.response_id,
                    type(exc).__name__,
                )

    async def run_in_force(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        action_id: RecordId,
        response_id: str,
    ) -> bool:
        """Whether the run still applies: the form has the action switched on and
        the response is still stored, in this workspace and on this form."""
        form_document = await self.form_repo.get_form_document_by_id(str(form_id))
        if form_document is None:
            return False
        on_submit = (form_document.actions or {}).get(Trigger.on_submit) or []
        if not any(
            str(configured.id) == str(action_id) and configured.enabled
            for configured in on_submit
        ):
            return False
        stored = await self.form_response_service.workspace_response(
            workspace_id, str(response_id)
        )
        return stored is not None and str(stored.form_id) == str(form_id)

    async def action_run_context(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        action_id: RecordId,
        response_id: str,
        plain_secrets: bool = False,
    ) -> Optional[dict]:
        """What the actions executor needs to run one queued action run, read
        now (the job carries ids only, never answers): the action, the
        published form with the action settings, the decrypted response, the
        workspace's copy of the action and the responder's identifier, each as
        JSON text, exactly as the run was once queued with them.

        None when the run must not happen any more: the response was deleted
        (erasure wins over a late run), the form, the action or the workspace's
        copy is gone, the action was switched off or taken off the form, or a
        Google Sheets action holds a legacy grant. The executor then skips the
        job instead of retrying it.

        With ``plain_secrets`` (an executor of 4.3 or later asks for it) this
        action's secrets arrive opened, and ``secrets_plain`` is true in the
        answer: the executor then needs no key. Otherwise they are sealed, as
        they are stored, and the executor opens them with its own copy of the key."""
        form_document = await self.form_repo.get_form_document_by_id(str(form_id))
        latest = await self.form_repo.get_latest_version_of_form(RecordId(str(form_id)))
        if form_document is None or latest is None:
            return None
        on_submit = (form_document.actions or {}).get(Trigger.on_submit) or []
        if not any(
            str(configured.id) == str(action_id) and configured.enabled
            for configured in on_submit
        ):
            return None
        stored = await self.form_response_service.workspace_response(
            workspace_id, str(response_id)
        )
        if stored is None or str(stored.form_id) != str(form_id):
            return None
        action = await self.action_repository.get_action_by_id(action_id)
        if action is None:
            return None
        if self.sheets_reconsent is not None and (
            await self.sheets_reconsent.hold_back_run(
                form_document, action, workspace_id
            )
        ):
            return None
        try:
            workspace = await self.workspace_repo.get_workspace_with_action_by_id(
                workspace_id=workspace_id, action_id=action.id
            )
        except AppHTTPException:
            return None
        workspace = WorkspaceRequestWithActionDto(**workspace)
        response = self.form_response_service.decrypt_form_response(
            workspace_id=workspace_id, response=stored
        )
        # the same form the run used to be queued with: the published version
        # with the action settings of the current one, as the respondent sees it
        latest.actions = form_document.actions
        latest.secrets = form_document.secrets
        latest.parameters = form_document.parameters
        form = strip_internal_fields(latest.model_copy(deep=True))
        # this action's settings only: not the secrets of the form's other actions
        form.secrets = _only(form.secrets, action.id)
        form.parameters = _only(form.parameters, action.id)
        workspace.secrets = _only(workspace.secrets, action.id)
        workspace.parameters = _only(workspace.parameters, action.id)
        if plain_secrets and self.crypto is not None:
            action = action.model_copy(
                update={"secrets": self._opened(action.secrets, action.id)}
            )
            for owner in (form, workspace):
                if owner.secrets:
                    owner.secrets = {
                        key: self._opened(values, action.id)
                        for key, values in owner.secrets.items()
                    }
            # the hand-out is on record: which run, how many, never a value
            handed = len(action.secrets or []) + sum(
                len(values or [])
                for owner in (form, workspace)
                for values in (owner.secrets or {}).values()
            )
            logger.info(
                "run secrets handed to the executor opened: workspace={} form={} "
                "action={} response={} count={}",
                workspace_id,
                form_id,
                action_id,
                response_id,
                handed,
            )
        else:
            plain_secrets = False
        answer = {
            "action": action.model_dump_json(),
            "form": form.model_dump_json(),
            "response": response.model_dump_json(),
            "user_email": response.dataOwnerIdentifier or "",
            "workspace": workspace.model_dump_json(),
        }
        if plain_secrets:
            answer["secrets_plain"] = True
        return answer

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
        if action.name == CREATOR_COPY_ACTION and recipient_values(action.parameters):
            # an instance-wide default would mail every workspace's responses
            # to one address; a form's copies go to its own members only
            raise not_allowed()
        return await self.action_repository.create_global_action(
            action=action, user=user
        )
