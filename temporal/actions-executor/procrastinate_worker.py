"""The actions-executor as a procrastinate worker (plans/postgres-consolidation.md §7).

Consumes the ``actions`` queue only, connecting as the ``bc_jobs_exec`` role
whose search_path is the ``jobs`` schema (it can reach the queue tables and
nothing else). The backend defers ``run_action`` by name; the body is here,
the same ``run_action`` the Temporal activity wraps. Selected by
``JOBS_BACKEND=postgres`` in main.py; the Temporal worker remains the default.
"""

import asyncio
import os

from procrastinate import App, PsycopgConnector, RetryStrategy

from utilities.actions import run_action

ACTIONS_QUEUE = "actions"


def libpq_url(url: str) -> str:
    scheme, _, rest = url.partition("://")
    return f"{scheme.split('+')[0]}://{rest}"


app = App(
    connector=PsycopgConnector(
        conninfo=libpq_url(os.environ.get("DATABASE_URL", "")),
        kwargs={"options": "-c search_path=jobs"},
        min_size=1,
        max_size=int(os.environ.get("JOBS_POOL_MAX", "4")),
    )
)


@app.task(name="run_action", queue=ACTIONS_QUEUE, retry=RetryStrategy(max_attempts=2))
async def run_action_job(
    action: str, form: str, response: str, user_email=None, workspace=None
):
    return await run_action(
        action=action,
        form=form,
        response=response,
        user_email=user_email,
        workspace=workspace,
    )


async def main() -> None:
    async with app.open_async():
        await app.run_worker_async(
            queues=[ACTIONS_QUEUE],
            concurrency=int(os.environ.get("JOBS_CONCURRENCY", "4")),
            install_signal_handlers=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
