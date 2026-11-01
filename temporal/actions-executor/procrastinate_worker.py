"""The actions-executor as a procrastinate worker.

Consumes the ``actions`` queue only, connecting as the ``bc_jobs_exec`` role
whose search_path is the ``jobs`` schema (it can reach the queue tables and
nothing else). The backend defers ``run_action`` by name with ids only; the
body is here and asks the backend for the run's data when it runs
(utilities/run_context.py), then calls the same ``run_action`` the Temporal
activity wraps. Selected by ``JOBS_BACKEND=postgres`` (the default) in main.py;
``JOBS_BACKEND=temporal`` runs the Temporal worker instead.

It refuses to start unless the database restricts its role to the ``actions``
queue's rows (utilities/queue_isolation.py).

Guarantees, as the Temporal workflow had them: a failed run is retried with a
growing wait (three attempts), a run is cut off after ``RUN_TIMEOUT_SECONDS``,
and the same run is queued once at a time (the backend's queueing lock).
Nothing of a run's data is logged or raised: a failure names the ids and the
kind of error, never a message, because the message of a creator's code or of
a provider can hold an answer.
"""

import asyncio
import logging
import os
from typing import Optional

from procrastinate import App, PsycopgConnector, RetryStrategy

from sandbox import broker
from settings.application import isolation_enforced, settings
from utilities.actions import run_action
from utilities.google_service import RunScope
from utilities.job_logging import scrub_job_logging
from utilities.queue_isolation import require_isolated_queue
from utilities.run_context import RunContextUnavailable, fetch_run_context

logger = logging.getLogger(__name__)

# no job argument in any log line (utilities/job_logging.py)
scrub_job_logging()

ACTIONS_QUEUE = "actions"
# procrastinate counts retries, not runs: two retries after the first run
MAX_RUNS = 3
RETRY_WAIT_BASE_SECONDS = 5  # waits of 5 s, then 25 s
RUN_TIMEOUT_SECONDS = 90


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


class ActionRunFailed(Exception):
    """A run that failed. The message holds ids and the error's class only."""


@app.task(
    name="run_action",
    queue=ACTIONS_QUEUE,
    retry=RetryStrategy(
        max_attempts=MAX_RUNS - 1, exponential_wait=RETRY_WAIT_BASE_SECONDS
    ),
)
async def run_action_job(
    action_id: Optional[str] = None,
    form_id: Optional[str] = None,
    response_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    run_token: Optional[str] = None,
    # jobs queued by 4.1.x carried the whole run; they are still run, once
    action: Optional[str] = None,
    form: Optional[str] = None,
    response: Optional[str] = None,
    user_email: Optional[str] = None,
    workspace: Optional[str] = None,
) -> str:
    try:
        if action_id is not None:
            context = await fetch_run_context(
                workspace_id, form_id, action_id, response_id, run_token
            )
            if context is None:
                logger.info(
                    "action run skipped, it no longer applies: action=%s form=%s",
                    action_id,
                    form_id,
                )
                return "skipped"
            action, form, response, workspace = (
                context["action"],
                context["form"],
                context["response"],
                context["workspace"],
            )
            user_email = context.get("user_email") or None
            secrets_plain = bool(context.get("secrets_plain"))
            run_scope = RunScope(
                workspace_id=str(workspace_id),
                form_id=str(form_id),
                action_id=str(action_id),
                response_id=str(response_id),
                run_token=str(run_token),
            )
        else:
            # a job queued by 4.1.x: the secrets in it are sealed
            secrets_plain, run_scope = False, None
        await asyncio.wait_for(
            run_action(
                action=action,
                form=form,
                response=response,
                user_email=user_email,
                workspace=workspace,
                secrets_plain=secrets_plain,
                run_scope=run_scope,
            ),
            timeout=RUN_TIMEOUT_SECONDS,
        )
    except Exception as error:  # noqa: BLE001 - re-raised without its message
        reason = (
            str(error)
            if isinstance(error, RunContextUnavailable)
            else type(error).__name__
        )
        raise ActionRunFailed(
            f"action run failed: action={action_id} form={form_id} ({reason})"
        ) from None
    return "ok"


async def log_isolation() -> None:
    """Say at start what the custom-code sandbox can do here (never fatal: a
    stack that runs only the built-in actions has no use for it, and a run of
    custom code fails closed when the child cannot confine itself)."""
    if not isolation_enforced():
        logger.error(
            "ACTION_ISOLATION=legacy: custom action code runs inside this process "
            "and can reach its keys. Unset it unless you are rolling back."
        )
        return
    broker.harden_parent()
    if settings.aes_hex_key:
        logger.warning(
            "AES_HEX_KEY is set on the executor: it is not used while the backend "
            "(4.3 or later) opens the run's secrets; remove it from this service"
        )
    try:
        facts = await broker.probe()
        logger.info(
            "action sandbox ready: filesystem=%s seccomp=%s unprivileged=%s",
            facts.get("filesystem"),
            facts.get("seccomp"),
            facts.get("unprivileged"),
        )
    except broker.SandboxUnavailable as error:
        logger.error(
            "action sandbox NOT available, custom action code will not run: %s "
            "(docs/executor-isolation.md)",
            error,
        )


async def main() -> None:
    await log_isolation()
    async with app.open_async():
        # fail closed: this role only runs where the database keeps it to its own queue
        await require_isolated_queue(app.connector)
        await app.run_worker_async(
            queues=[ACTIONS_QUEUE],
            concurrency=int(os.environ.get("JOBS_CONCURRENCY", "4")),
            install_signal_handlers=True,
        )


if __name__ == "__main__":
    from settings.application import log_if_api_key_missing

    log_if_api_key_missing()
    asyncio.run(main())
