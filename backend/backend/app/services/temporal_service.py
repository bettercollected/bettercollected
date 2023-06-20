import json
from dataclasses import asdict
from http import HTTPStatus

import loguru
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.user_tokens import UserTokens
from common.build.lib.utils.asyncio_run import asyncio_run
from common.configs.crypto import Crypto


class TemporalService:
    def __init__(self, server_uri: str, namespace: str, crypto: Crypto):
        try:
            self.crypto = crypto
            self.client: Client = asyncio_run(
                Client.connect(server_uri, namespace=namespace)
            )
            loguru.logger.info("Temporal Server Connected Successfully")
        except Exception as e:
            self.client = None
            loguru.logger.error("Could not connect to Temporal server")

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
                task_queue="delete_user",
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
