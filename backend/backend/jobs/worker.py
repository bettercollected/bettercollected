"""The backend's job worker: ``python -m backend.jobs.worker``.

Same image and configuration as the API; boots the container (Beanie, the
Postgres engine, the outbox) and consumes the ``default`` queue — never
``actions``, which belongs to the actions-executor. Concurrency is small on
purpose (jobs are deletions).
"""

from __future__ import annotations

import asyncio
import os

from dependency_injector import providers
from loguru import logger
from pymongo import AsyncMongoClient

from backend.app.container import container
from backend.app.handlers.database import close_db, init_db
from backend.app.utils import AiohttpClient
from backend.config import settings
from backend.db.startup import check_postgres_at_startup, dispose_postgres
from backend.jobs.app import DEFAULT_QUEUE, app


async def main() -> None:
    queues = [q for q in os.environ.get("JOBS_QUEUES", DEFAULT_QUEUE).split(",") if q]
    concurrency = int(os.environ.get("JOBS_CONCURRENCY", "4"))
    AiohttpClient.get_aiohttp_client()
    client = AsyncMongoClient(settings.mongo_settings.URI)
    container.database_client.override(providers.Object(client))
    await init_db(settings.mongo_settings.DB, client)
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
