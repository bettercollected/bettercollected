import asyncio
import os
import random
import string

from temporalio.client import Client
from temporalio.worker import Worker

from activities.run_action_code import run_action_code
from settings.application import settings
from workflows.run_action_code import RunActionCode


def get_random_string(length=20):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


async def run_worker():
    client = await Client.connect(
        settings.temporal_server_url, namespace=settings.namespace
    )
    worker = Worker(
        client,
        identity=get_random_string(),
        task_queue=settings.worker_queue,
        workflows=[RunActionCode],
        activities=[run_action_code],
    )
    await worker.run()


async def main():
    workers = [run_worker() for i in range(0, settings.workers)]
    await asyncio.gather(*workers)


if __name__ == "__main__":
    # JOBS_BACKEND=postgres: consume the procrastinate `actions` queue instead
    # of Temporal (plans/postgres-consolidation.md §7). Temporal stays default.
    if os.environ.get("JOBS_BACKEND", "temporal").lower() == "postgres":
        from procrastinate_worker import main as run_procrastinate

        asyncio.run(run_procrastinate())
    else:
        asyncio.run(main())
