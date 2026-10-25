"""Job bodies. They call the same service methods the Temporal workers reach
today over HTTP (``/auth/user``, ``/temporal/delete/submissions/…``) — in
process, no HTTP hop, no API key. ``run_action`` is deliberately *not* defined
here: the backend only defers it by name; the actions-executor process owns
the body (temporal/actions-executor/procrastinate_worker.py) and is the only
consumer of the ``actions`` queue.
"""

from __future__ import annotations

from dataclasses import asdict

from loguru import logger
from procrastinate import RetryStrategy

from backend.app.services.credential_purge import (
    PURGE_ATTEMPTS,
    PURGE_RETRY_SECONDS,
    CredentialPurgeFailed,
)
from backend.app.services.google_grant_revocation import (
    REVOKE_ATTEMPTS,
    REVOKE_RETRY_SECONDS,
    GrantRevocationFailed,
)
from backend.app.services.user_service import user_for_deletion
from backend.config import settings
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
    name="purge_provider_credentials",
    queue=DEFAULT_QUEUE,
    # only an attempt that may pass later is retried (a refused request or an
    # unreadable argument fails once, visibly)
    retry=RetryStrategy(
        max_attempts=PURGE_ATTEMPTS,
        wait=PURGE_RETRY_SECONDS,
        retry_exceptions={CredentialPurgeFailed},
    ),
)
async def purge_provider_credentials(sealed: str, user_id: str) -> str:
    """Erase a deleted account's stored provider credentials. Written by
    release 4.1's deletion when the provider service could not be reached; kept
    here so a stack rolled back from 4.1 finishes the erasure (one attempt,
    retried hourly for two days). ``sealed`` is the encrypted CredentialPurge."""
    from backend.app.services.credential_purge import unseal

    container = _container()
    purge = unseal(container.crypto(), sealed)
    if purge.user_id != user_id:
        raise ValueError("purge request does not match the job's user")
    return await container.credential_purge_service().purge(purge)


@app.task(
    name="revoke_google_grant",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(
        max_attempts=REVOKE_ATTEMPTS,
        wait=REVOKE_RETRY_SECONDS,
        retry_exceptions={GrantRevocationFailed},
    ),
)
async def revoke_google_grant(sealed: str, form_id: str, action_id: str) -> str:
    """Revoke at Google the old grant a Google Sheets action held. Written by
    release 4.1 when Google could not be reached at the moment of the
    re-consent; kept here so a stack rolled back from 4.1 finishes the
    revocation (one attempt, retried hourly for two days). ``sealed`` is the
    encrypted GrantRevocation."""
    from backend.app.services.google_grant_revocation import unseal

    container = _container()
    revocation = unseal(container.crypto(), sealed)
    if (revocation.form_id, revocation.action_id) != (form_id, action_id):
        raise ValueError("revocation request does not match the job's action")
    return await container.google_grant_service().revoke(revocation)


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
    import_id = PydanticObjectId(import_id)
    try:
        # the heartbeat keeps a long stage from looking interrupted
        record = await pipeline.keep_alive(import_id, pipeline.run(import_id))
    except SandboxUnavailable:
        if context.job.attempts + 1 < IMPORT_FORM_ATTEMPTS:
            raise
        record = await pipeline.give_up(import_id)
    return record.status if record else "missing"


@app.periodic(
    cron=settings.pdf_import.STALE_SWEEP_CRON, periodic_id="expire_stale_imports"
)
@app.task(
    name="expire_stale_imports",
    queue=DEFAULT_QUEUE,
    queueing_lock="expire_stale_imports",
)
async def expire_stale_imports(timestamp: int) -> str:
    """Fail form imports whose job died mid-run (no heartbeat for
    ``PDF_IMPORT_STALE_AFTER_S``) so they free their workspace's import slot
    (#703). Starting an import and looking at one expire them too; this sweep
    only makes sure nothing stays "running" in between."""
    expired = await _container().pdf_import_service().expire_stale_everywhere()
    return f"{expired} expired"


@app.periodic(cron=settings.scim.RECONCILE_CRON, periodic_id="scim_reconcile")
@app.task(
    name="scim_reconcile",
    queue=DEFAULT_QUEUE,
    queueing_lock="scim_reconcile",
    retry=RetryStrategy(max_attempts=2, exponential_wait=60),
)
async def scim_reconcile(timestamp: int) -> str:
    """Nightly SCIM resync of every workspace directory (docs/sso.md): pulls
    users and groups from Polis and applies them, catching webhook events
    that never arrived. Runs wherever the procrastinate worker runs; without
    it, use the admin button or ``python -m backend.scim resync --all``."""
    result = await _container().scim_directory_service().resync_all("schedule")
    return f"{result['directories']} resynced, {result['failed']} failed"


# Periodic jobs release 4.1 schedules and this release does not run. A row one
# left in the queue completes here instead of failing as an unknown task; they
# are not scheduled again (no ``app.periodic``), so a rolled-back stack never
# repeats them, and they touch nothing release 4.0 does not support.
@app.task(name="sso_release_retry", queue=DEFAULT_QUEUE)
async def sso_release_retry(timestamp: int = 0) -> str:
    """4.1's daily release of the Polis connections of deleted workspaces.
    Nothing here: connections it was waiting on keep their ``release_pending``
    status (they never sign anyone in) until 4.1 runs again."""
    logger.info("sso_release_retry: release 4.1 job, nothing to do on this release")
    return "skipped"


@app.task(name="recheck_verified_domains", queue=DEFAULT_QUEUE)
async def recheck_verified_domains(timestamp: int = 0) -> str:
    """4.1's hourly re-check of verified email domains. This release has the
    service method but no schedule (docs/verified-domains.md), so a single
    leftover row does not start one: domains are re-checked again when 4.1
    runs."""
    logger.info(
        "recheck_verified_domains: release 4.1 job, nothing to do on this release"
    )
    return "skipped"


def run_action_deferrer(queueing_lock: str):
    """Defer ``run_action`` to the actions queue without importing its body."""
    return app.configure_task(
        name=RUN_ACTION, queue=ACTIONS_QUEUE, queueing_lock=queueing_lock
    )
