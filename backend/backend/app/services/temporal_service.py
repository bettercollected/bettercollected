import json
from dataclasses import asdict
from datetime import timedelta
from http import HTTPStatus

import loguru
from beanie import PydanticObjectId
from common.configs.crypto import Crypto
from common.models.standard_form import StandardFormResponse, StandardForm
from common.utils.asyncio_run import asyncio_run
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleIntervalSpec,
    ScheduleUpdateInput,
    ScheduleUpdate,
    ScheduleAlreadyRunningError,
)
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.delete_response_params import DeleteResponseParams
from backend.app.models.dataclasses.import_form_params import ImportFormParams
from backend.app.models.dataclasses.run_action_code_params import RunActionCodeParams
from backend.app.models.dataclasses.save_preview_params import SavePreviewParams
from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.app.schemas.action_document import ActionDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.utils.date_utils import get_formatted_date_from_str
from backend.config import settings


class TemporalService:
    def __init__(self, server_uri: str, namespace: str, crypto: Crypto):
        self.server_uri = server_uri
        self.namespace = namespace
        self.crypto = crypto
        self.temporal_client = None
        if settings.schedular_settings.ENABLED:
            self.connect_to_temporal_server(server_uri=server_uri, namespace=namespace)

    def connect_to_temporal_server(self, server_uri: str, namespace: str):
        try:
            self.temporal_client: Client = asyncio_run(
                Client.connect(server_uri, namespace=namespace)
            )
        except Exception as e:
            self.temporal_client: Client = None
            loguru.logger.error("Could not connect to Temporal server", e)

    async def check_temporal_client_and_try_to_connect_if_not_connected(self):
        if not self.temporal_client:
            self.connect_to_temporal_server(self.server_uri, self.namespace)
            if not self.temporal_client:
                raise HTTPException(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    content="Cannot connect to temporal server",
                )

    async def start_user_deletion_workflow(self, user_tokens: UserTokens, user_id: str):
        await self.check_temporal_client_and_try_to_connect_if_not_connected()
        try:
            encrypted_tokens = self.crypto.encrypt(json.dumps(asdict(user_tokens)))
            await self.temporal_client.start_workflow(
                "delete_user_workflow",
                encrypted_tokens,
                id="delete_user_" + user_id,
                task_queue=settings.temporal_settings.worker_queue,
                retry_policy=RetryPolicy(maximum_attempts=4),
            )
            return "Workflow Started"

        except WorkflowAlreadyStartedError as e:
            loguru.logger.error(
                "Workflow with id: delete_user_"
                + user_id
                + " has already been started."
            )
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT, content="Workflow has already started."
            )

    async def start_save_preview_workflow(self, template_id: PydanticObjectId, user_tokens: UserTokens):
        await self.check_temporal_client_and_try_to_connect_if_not_connected()
        try:
            encrypted_tokens = self.crypto.encrypt(json.dumps(asdict(user_tokens)))
            params = SavePreviewParams(template_id=str(template_id),
                                       template_url=f"{settings.api_settings.CLIENT_URL}/templates/" + str(
                                           template_id) + "/preview",
                                       token=encrypted_tokens)
            await self.temporal_client.start_workflow("save_template_preview",
                                                      arg=params,
                                                      id="save_preview_image_" + str(template_id),
                                                      task_queue=settings.temporal_settings.worker_queue,
                                                      retry_policy=RetryPolicy(maximum_attempts=4)
                                                      )
            return "Workflow Started"
        except WorkflowAlreadyStartedError as e:
            loguru.logger.info("Workflow has already started")

    async def add_scheduled_job_for_importing_form(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        if not settings.schedular_settings.ENABLED:
            return
        try:
            await self.check_temporal_client_and_try_to_connect_if_not_connected()
            await self.temporal_client.create_schedule(
                "import_" + str(workspace_id) + "_" + form_id,
                schedule=Schedule(
                    action=ScheduleActionStartWorkflow(
                        "import_form_workflow",
                        id="import_form_" + form_id,
                        arg=ImportFormParams(
                            workspace_id=str(workspace_id), form_id=form_id
                        ),
                        task_queue=settings.temporal_settings.worker_queue,
                    ),
                    spec=ScheduleSpec(
                        intervals=[
                            ScheduleIntervalSpec(
                                every=timedelta(
                                    minutes=settings.schedular_settings.INTERVAL_MINUTES
                                )
                            )
                        ],
                    ),
                ),
            )
        except ScheduleAlreadyRunningError as e:
            loguru.logger.info(e)
        except HTTPException as e:
            if e.status_code != HTTPStatus.SERVICE_UNAVAILABLE:
                loguru.logger.error(e)
        except Exception as e:
            loguru.logger.error(e)

    async def add_scheduled_job_for_deleting_response(
        self, response: StandardFormResponse
    ):
        if not settings.schedular_settings.ENABLED:
            return
        expiration_date = get_formatted_date_from_str(response.expiration)
        try:
            await self.check_temporal_client_and_try_to_connect_if_not_connected()
            await self.temporal_client.create_schedule(
                "delete_response_" + str(response.response_id),
                schedule=Schedule(
                    action=ScheduleActionStartWorkflow(
                        "delete_response_workflow",
                        id="delete_response_" + response.response_id,
                        arg=DeleteResponseParams(
                            response_id=response.response_id,
                        ),
                        task_queue=settings.temporal_settings.worker_queue,
                        retry_policy=RetryPolicy(maximum_attempts=4),
                    ),
                    spec=ScheduleSpec(
                        cron_expressions=[
                            f"{expiration_date.second} {expiration_date.minute} {expiration_date.hour} {expiration_date.day} {expiration_date.month} {expiration_date.isoweekday()} {expiration_date.year}"
                        ]
                    ),
                ),
            )
        except ScheduleAlreadyRunningError as e:
            loguru.logger.info(e)
        except HTTPException as e:
            if e.status_code != HTTPStatus.SERVICE_UNAVAILABLE:
                loguru.logger.error(e)
        except Exception as e:
            loguru.logger.error(e)

    async def delete_form_import_schedule(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        if not settings.schedular_settings.ENABLED:
            return
        try:
            await self.check_temporal_client_and_try_to_connect_if_not_connected()
            schedule_id = "import_" + str(workspace_id) + "_" + form_id
            schedule_handle = self.temporal_client.get_schedule_handle(schedule_id)
            await schedule_handle.delete()

        except HTTPException:
            pass
        except RPCError as e:
            loguru.logger.info(
                "No schedule found for id:" + str(schedule_id) + " to delete"
            )
            pass

    async def delete_response_delete_schedule(self, response_id: str):
        if not settings.schedular_settings.ENABLED:
            return
        try:
            await self.check_temporal_client_and_try_to_connect_if_not_connected()
            schedule_id = "delete_response_" + response_id
            schedule_handle = self.temporal_client.get_schedule_handle(schedule_id)
            await schedule_handle.delete()

        except HTTPException:
            pass
        except RPCError as e:
            loguru.logger.info(
                "No schedule found for id:" + str(schedule_id) + " to delete"
            )
            pass

    def update_schedule_interval(self, interval: timedelta):
        async def update_interval_to_default(
            update_input: ScheduleUpdateInput,
        ) -> ScheduleUpdate:
            schedule_spec = update_input.description.schedule.spec
            if isinstance(schedule_spec, ScheduleSpec):
                schedule_spec.intervals = [ScheduleIntervalSpec(every=interval)]
            return ScheduleUpdate(schedule=update_input.description.schedule)

        return update_interval_to_default

    async def update_interval_of_schedule(
        self, workspace_id: PydanticObjectId, form_id: str, interval: timedelta
    ):
        handle = self.temporal_client.get_schedule_handle(
            "import_" + str(workspace_id) + "_" + form_id
        )
        await handle.update(updater=self.update_schedule_interval(interval=interval))

    async def start_action_execution(self, action: ActionDocument, form: StandardForm, response: FormResponseDocument):
        if not settings.schedular_settings.ENABLED:
            return
        run_action_params = RunActionCodeParams(action=action.json(), form=form.json(), response=response.json(),
                                                user_email=response.dataOwnerIdentifier if response is not None else "")
        try:
            await self.check_temporal_client_and_try_to_connect_if_not_connected()
            await self.temporal_client.start_workflow(
                "run_action_code",
                arg=run_action_params,
                id="action_" + str(action.id) + str(form.form_id) + str(response.response_id),
                task_queue=settings.temporal_settings.action_queue
            )
            return "Workflow Started"
        except WorkflowAlreadyStartedError as e:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT, content="Workflow has already started."
            )
