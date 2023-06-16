from http import HTTPStatus

import loguru
from temporalio.client import Client
from temporalio.common import RetryPolicy

from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.user_tokens import UserTokens
from common.build.lib.utils.asyncio_run import asyncio_run


class TemporalService:
    def __init__(self, server_uri: str):
        try:

            self.client: Client = asyncio_run(Client.connect(server_uri))
        except Exception as e:
            loguru.Logger.info("Could not connect to Temporal server")

    async def start_user_deletion_workflow(self, user_tokens: UserTokens, user_id: str):
        if not self.client:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Cannot connect to temporal server",
            )
        await self.client.start_workflow(
            "delete_user_workflow",
            user_tokens,
            id="delete_user_" + user_id,
            task_queue="delete_user",
            retry_policy=RetryPolicy(maximum_attempts=4),
        )
        return "Workflow Started"
