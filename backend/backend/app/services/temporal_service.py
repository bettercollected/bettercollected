import json
from dataclasses import asdict
from datetime import timedelta, timezone
from http import HTTPStatus
from typing import List, Optional

from procrastinate import App
from procrastinate.exceptions import AlreadyEnqueued

from common.db.flags import DbFlags, JobsBackend
from backend.jobs import tasks
from bson import ObjectId

import loguru
from beanie import PydanticObjectId
from common.configs.crypto import Crypto
from common.models.standard_form import StandardFormResponse, StandardForm
from common.models.user import User
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
from backend.app.models.dataclasses.export_to_csv import ExportCSVParams
from backend.app.models.dataclasses.import_form_params import ImportFormParams
from backend.app.models.dataclasses.run_action_code_params import RunActionCodeParams
from backend.app.models.dataclasses.save_preview_params import SavePreviewParams
from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.app.models.dtos.action_dto import ActionResponse
from backend.app.models.workspace import WorkspaceRequestWithActionDto
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.utils.date_utils import get_formatted_date_from_str
from backend.config import settings


class TemporalService:
    """Starts background jobs. Per job kind, ``JOBS_BACKEND__<job>`` picks the
    Temporal workflow (today's default) or a procrastinate job on Postgres
    (plans/postgres-consolidation.md §7); the callers do not know which."""

    def __init__(
        self,
        server_uri: str,
        namespace: str,
        crypto: Crypto,
        flags: Optional[DbFlags] = None,
        jobs: Optional[App] = None,
    ):
        self.server_uri = server_uri
        self.namespace = namespace
        self.crypto = crypto
        # Connect lazily on first use (see
        # check_temporal_client_and_try_to_connect_if_not_connected), on the
        # main event loop where the client is awaited, rather than eagerly here
        # via asyncio_run's background loop. The temporalio client binds to the
        # loop it's created on; connecting off the request loop is a latent
        # cross-loop hazard (the same shape that broke the auth OTP send once
        # motor's cross-loop tolerance was dropped for pymongo).
        self.temporal_client = None
        self.flags = flags
        self.jobs = jobs

    def _on_postgres(self, job: str) -> bool:
        return (
            self.flags is not None
            and self.jobs is not None
            and self.flags.jobs_backend(job) is JobsBackend.POSTGRES
        )

    async def connect_to_temporal_server(self):
        try:
            self.temporal_client: Client = await Client.connect(
                self.server_uri, namespace=self.namespace
            )
        except Exception as e:
            self.temporal_client: Client = None
            loguru.logger.error("Could not connect to Temporal server", e)

    async def check_temporal_client_and_try_to_connect_if_not_connected(self):
        if not self.temporal_client:
            await self.connect_to_temporal_server()
            if not self.temporal_client:
                raise HTTPException(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    content="Cannot connect to temporal server",
                )

    async def start_user_deletion_workflow(self, user_tokens: UserTokens, user_id: str):
        encrypted_tokens = self.crypto.encrypt(json.dumps(asdict(user_tokens)))
        if self._on_postgres("delete_user"):
            try:
                await tasks.delete_user.configure(
                    queueing_lock=f"delete_user:{user_id}"
                ).defer_async(encrypted_tokens=encrypted_tokens, user_id=user_id)
                return "Job Started"
            except AlreadyEnqueued:
                loguru.logger.error(
                    "Deletion of user " + user_id + " has already been queued."
                )
                return None
        await self.check_temporal_client_and_try_to_connect_if_not_connected()
        try:
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

    async def add_scheduled_job_for_deleting_response(
        self, response: StandardFormResponse
    ):
        expiration_date = get_formatted_date_from_str(response.expiration)
        if self._on_postgres("delete_response"):
            try:
                await tasks.delete_response.configure(
                    schedule_at=expiration_date.replace(tzinfo=timezone.utc),
                    queueing_lock=f"delete_response:{response.response_id}",
                ).defer_async(response_id=response.response_id)
            except AlreadyEnqueued as e:
                loguru.logger.info(e)
            return
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

    async def delete_response_delete_schedule(self, response_id: str):
        if self._on_postgres("delete_response"):
            pending = await self.jobs.job_manager.list_jobs_async(
                queueing_lock=f"delete_response:{response_id}", status="todo"
            )
            for job in pending:
                await self.jobs.job_manager.cancel_job_by_id_async(
                    job.id, delete_job=True
                )
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

    async def start_action_execution(
        self,
        action: ActionResponse,
        form: StandardForm,
        response: FormResponseDocument,
        workspace: WorkspaceRequestWithActionDto,
    ):

        workspace = WorkspaceRequestWithActionDto(**workspace)
        run_action_params = RunActionCodeParams(
            action=action.json(),
            form=form.json(),
            response=response.json(),
            user_email=response.dataOwnerIdentifier if response is not None else "",
            workspace=workspace.json(),
        )
        lock = (
            "action_" + str(action.id) + str(form.form_id) + str(response.response_id)
        )
        if self._on_postgres("run_action"):
            try:
                await tasks.run_action_deferrer(queueing_lock=lock).defer_async(
                    **asdict(run_action_params)
                )
                return "Job Started"
            except AlreadyEnqueued:
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    content="Workflow has already started.",
                )
        try:
            await self.check_temporal_client_and_try_to_connect_if_not_connected()
            await self.temporal_client.start_workflow(
                "run_action_code",
                arg=run_action_params,
                id="action_"
                + str(action.id)
                + str(form.form_id)
                + str(response.response_id),
                task_queue=settings.temporal_settings.action_queue,
            )
            return "Workflow Started"
        except WorkflowAlreadyStartedError as e:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT, content="Workflow has already started."
            )
