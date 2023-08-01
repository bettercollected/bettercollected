import json
from dataclasses import asdict
from datetime import timedelta
from http import HTTPStatus

import loguru
from beanie import PydanticObjectId
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleIntervalSpec,
)
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.ImportFormParams import ImportFormParams
from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.config import settings
from common.configs.crypto import Crypto
from common.utils.asyncio_run import asyncio_run


class TemporalService:
    def __init__(self, server_uri: str, namespace: str, crypto: Crypto):
        try:
            self.crypto = crypto
            self.client: Client = asyncio_run(
                Client.connect(server_uri, namespace=namespace)
            )
        except Exception as e:
            self.client: Client = None
            loguru.logger.error("Could not connect to Temporal server", e)

    async def start_user_deletion_workflow(self, user_tokens: UserTokens, user_id: str):
        if not self.client:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Cannot connect to temporal server",
            )
        try:
            encrypted_tokens = self.crypto.encrypt(json.dumps(asdict(user_tokens)))
            await self.client.start_workflow(
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

    async def add_scheduled_job_for_importing_form(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        if not self.client:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Cannot connect to temporal server",
            )

        try:
            await self.client.create_schedule(
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
                        intervals=[ScheduleIntervalSpec(every=timedelta(seconds=30))],
                    ),
                ),
            )
        except Exception as e:
            loguru.logger.error(e)
