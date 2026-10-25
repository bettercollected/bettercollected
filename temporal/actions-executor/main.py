import asyncio
import os
import random
import string

from temporalio.client import Client
from temporalio.worker import Worker

from activities.run_action_code import run_action_code
from settings.application import log_if_api_key_missing, settings
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


def jobs_backend(env=os.environ) -> str:
    """Where the worker takes its jobs from: ``postgres`` (the procrastinate
    ``actions`` queue; the default, as in the backend's ``common.db.flags``) or
    ``temporal`` (the ``RunActionCode`` workflow)."""
    value = (env.get("JOBS_BACKEND") or "postgres").strip().lower()
    if value not in ("postgres", "temporal"):
        raise SystemExit(f"JOBS_BACKEND must be postgres or temporal, got {value!r}")
    return value


def require_database_url(env=os.environ) -> None:
    """The Postgres queue needs the jobs role's URL: exit at start, naming the
    setting, instead of failing on the first connection (a restart loop that
    leaves ``run_action`` jobs without a consumer). Never echoes the value."""
    if not (env.get("DATABASE_URL") or "").strip():
        raise SystemExit(
            "JOBS_BACKEND is postgres (the default) but DATABASE_URL is not set: set it "
            "to the actions executor's jobs role URL (bc_jobs_exec), or set "
            "JOBS_BACKEND=temporal to keep the Temporal workflow."
        )


if __name__ == "__main__":
    log_if_api_key_missing()
    # JOBS_BACKEND=postgres (the default): consume the procrastinate `actions`
    # queue instead of Temporal (plans/postgres-consolidation.md §7);
    # JOBS_BACKEND=temporal keeps the workflow.
    if jobs_backend() == "postgres":
        require_database_url()
        from procrastinate_worker import main as run_procrastinate

        asyncio.run(run_procrastinate())
    else:
        asyncio.run(main())
