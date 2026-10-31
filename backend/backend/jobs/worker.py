"""The backend's job worker: ``python -m backend.jobs.worker``.

Same image and configuration as the API; boots the container (the Postgres
engine; Mongo is not used) and consumes the ``default``, ``webhooks``, ``emails`` and ``exports`` queues — never
``actions``, which belongs to the actions-executor. Concurrency is small on
purpose (jobs are deletions).
"""

from __future__ import annotations

import asyncio
import os

from common.settings.loader.source import set_instance_role

# the settings heartbeat of this process is labelled "backend.jobs:<host>", so the
# admin portal's Health page shows the worker apart from the API (set before the
# settings load below, which starts the heartbeat)
set_instance_role("jobs")

from loguru import logger

from backend.config import settings  # first of ours: it loads the settings snapshot
from backend.app.container import container
from backend.app.services.internal_auth import log_if_internal_key_missing
from backend.app.services.email_actions.mode import email_actions_enabled
from backend.app.services.webhooks.mode import webhooks_enabled
from backend.app.utils import AiohttpClient
from backend.db.startup import check_postgres_at_startup, dispose_postgres
from backend.jobs.app import DEFAULT_QUEUE, EMAILS_QUEUE, EXPORTS_QUEUE, WEBHOOKS_QUEUE, app
from common.services.crypto_service import crypto_service


def warn_if_webhooks_unserved(queues: list) -> bool:
    """Webhooks are on but ``JOBS_QUEUES`` leaves out the ``webhooks`` queue:
    deliveries would be queued and never sent. Warns (True) at worker start."""
    if not webhooks_enabled() or WEBHOOKS_QUEUE in queues:
        return False
    logger.warning(
        "WEBHOOKS_ENABLED is on but this worker does not serve the '{}' queue "
        "(JOBS_QUEUES={}): webhook deliveries stay queued until a worker "
        "serves it. Add '{}' to JOBS_QUEUES.",
        WEBHOOKS_QUEUE,
        ",".join(queues),
        WEBHOOKS_QUEUE,
    )
    return True


def warn_if_emails_unserved(queues: list) -> bool:
    """Email actions are on but ``JOBS_QUEUES`` leaves out the ``emails``
    queue: mails would be queued and never sent. Warns (True) at worker start."""
    if not email_actions_enabled() or EMAILS_QUEUE in queues:
        return False
    logger.warning(
        "EMAIL_ACTIONS_ENABLED is on but this worker does not serve the '{}' queue "
        "(JOBS_QUEUES={}): emails stay queued until a worker serves it. Add '{}' "
        "to JOBS_QUEUES.",
        EMAILS_QUEUE,
        ",".join(queues),
        EMAILS_QUEUE,
    )
    return True


def warn_if_exports_unserved(queues: list) -> bool:
    """``JOBS_QUEUES`` leaves out the ``exports`` queue: the file of a large
    responses export would be queued and never built. Warns (True) at worker start."""
    if EXPORTS_QUEUE in queues:
        return False
    logger.warning(
        "this worker does not serve the '{}' queue (JOBS_QUEUES={}): large "
        "response exports stay queued until a worker serves it. Add '{}' to "
        "JOBS_QUEUES, here or on a worker of its own.",
        EXPORTS_QUEUE,
        ",".join(queues),
        EXPORTS_QUEUE,
    )
    return True


async def main() -> None:
    queues = [
        q
        for q in os.environ.get(
            "JOBS_QUEUES", f"{DEFAULT_QUEUE},{WEBHOOKS_QUEUE},{EMAILS_QUEUE},{EXPORTS_QUEUE}"
        ).split(",")
        if q
    ]
    concurrency = int(os.environ.get("JOBS_CONCURRENCY", "4"))
    log_if_internal_key_missing()  # delete_user removes the account in auth
    crypto_service.load()  # the response keyset: fail at startup when there is none
    AiohttpClient.get_aiohttp_client()
    await check_postgres_at_startup(container)
    logger.info("jobs worker: queues={} concurrency={}", queues, concurrency)
    warn_if_webhooks_unserved(queues)
    warn_if_emails_unserved(queues)
    warn_if_exports_unserved(queues)
    try:
        async with app.open_async():
            await app.run_worker_async(
                queues=queues, concurrency=concurrency, install_signal_handlers=True
            )
    finally:
        await dispose_postgres(container)
        await AiohttpClient.close_aiohttp_client()


if __name__ == "__main__":
    asyncio.run(main())
