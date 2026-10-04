"""Job bodies. They call the same service methods the Temporal workers reach
today over HTTP (``/auth/user``, ``/temporal/delete/submissions/…``) — in
process, no HTTP hop, no API key. ``run_action`` is deliberately *not* defined
here: the backend only defers it by name; the actions-executor process owns
the body (temporal/actions-executor/procrastinate_worker.py) and is the only
consumer of the ``actions`` queue.
"""

from __future__ import annotations

from dataclasses import asdict

from procrastinate import RetryStrategy

from backend.app.services.user_service import user_for_deletion
from backend.jobs.app import ACTIONS_QUEUE, DEFAULT_QUEUE, app

RUN_ACTION = "run_action"


def _container():
    from backend.app.container import container  # at call time: importing app boots it

    return container


@app.task(
    name="delete_user",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(max_attempts=4, exponential_wait=2),
)
async def delete_user(encrypted_tokens: str, user_id: str) -> str:
    """The user's workspaces, forms, integrations, auth record and
    sessions — what the Temporal `delete_user` activity does via
    DELETE /auth/user. ``encrypted_tokens`` (historical name) is the
    encrypted ``UserDeletion`` naming the account; no token is involved, so the
    job works however long ago the user signed out."""
    container = _container()
    user = user_for_deletion(encrypted_tokens)
    if user.id != user_id:
        raise ValueError("deletion request does not match the job's user")
    await container.auth_service().delete_user(user=user)
    return "User Deleted Successfully"


@app.task(
    name="delete_response",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(max_attempts=4, exponential_wait=2),
)
async def delete_response(response_id: str) -> str:
    """Scheduled at the response's expiration (`schedule_at`); one-shot, so
    unlike the Temporal path there is no schedule left to delete afterwards."""
    await _container().form_response_service().delete_response(response_id=response_id)
    return response_id


IMPORT_FORM_ATTEMPTS = 3


@app.task(
    name="import_form",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(max_attempts=IMPORT_FORM_ATTEMPTS, exponential_wait=5),
    pass_context=True,
)
async def import_form(context, import_id: str) -> str:
    """Run (or resume) a PDF form import; finished stages are checkpointed on
    the import record, so a retry only redoes the stage that failed. On the
    last attempt an unreachable sandbox fails the import instead of leaving
    it queued."""
    from beanie import PydanticObjectId

    from backend.app.services.pdf_import.sandbox import SandboxUnavailable

    pipeline = _container().pdf_import_pipeline()
    try:
        record = await pipeline.run(PydanticObjectId(import_id))
    except SandboxUnavailable:
        if context.job.attempts + 1 < IMPORT_FORM_ATTEMPTS:
            raise
        record = await pipeline.give_up(PydanticObjectId(import_id))
    return record.status if record else "missing"


def run_action_deferrer(queueing_lock: str):
    """Defer ``run_action`` to the actions queue without importing its body."""
    return app.configure_task(
        name=RUN_ACTION, queue=ACTIONS_QUEUE, queueing_lock=queueing_lock
    )
