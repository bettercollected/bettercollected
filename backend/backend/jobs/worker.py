"""The backend's job worker: ``python -m backend.jobs.worker``.

Same image and configuration as the API; boots the container (Beanie, the
Postgres engine, the outbox; Mongo only while a repository group uses it) and consumes the ``default`` queue — never
``actions``, which belongs to the actions-executor. Concurrency is small on
purpose (jobs are deletions).
"""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from backend.config import settings  # first: it loads the settings snapshot
from backend.app.container import container
from backend.app.handlers.database import close_db, open_mongo
from backend.app.services.internal_auth import log_if_internal_key_missing
from backend.app.utils import AiohttpClient
from backend.db.startup import (
    check_postgres_at_startup,
    dispose_postgres,
    mongo_required,
)
from backend.jobs.app import DEFAULT_QUEUE, app
from common.services.crypto_service import crypto_service


async def main() -> None:
    queues = [q for q in os.environ.get("JOBS_QUEUES", DEFAULT_QUEUE).split(",") if q]
    concurrency = int(os.environ.get("JOBS_CONCURRENCY", "4"))
    log_if_internal_key_missing()  # delete_user removes the account in auth
    crypto_service.load()  # the response keyset: fail at startup when there is none
    AiohttpClient.get_aiohttp_client()
    client = await open_mongo(
        container,
        settings.mongo_settings.URI,
        settings.mongo_settings.DB,
        required=mongo_required(container),
    )
    await check_postgres_at_startup(container)
    logger.info("jobs worker: queues={} concurrency={}", queues, concurrency)
    try:
        async with app.open_async():
            await app.run_worker_async(
                queues=queues, concurrency=concurrency, install_signal_handlers=True
            )
    finally:
        await close_db(client)
        await dispose_postgres(container)
        await AiohttpClient.close_aiohttp_client()


if __name__ == "__main__":
    asyncio.run(main())
