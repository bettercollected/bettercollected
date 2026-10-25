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

from backend.app.services.credential_purge import PURGE_ATTEMPTS, PURGE_RETRY_SECONDS
from backend.app.services.sheets_grant_revocation import (
    REVOKE_ATTEMPTS,
    REVOKE_RETRY_SECONDS,
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
    retry=RetryStrategy(max_attempts=PURGE_ATTEMPTS, wait=PURGE_RETRY_SECONDS),
)
async def purge_provider_credentials(sealed: str, user_id: str) -> str:
    """Erase a deleted account's stored provider credentials (one attempt;
    retried hourly for two days, then failed and reported by the admin
    portal's integrity monitor). ``sealed`` is the encrypted CredentialPurge."""
    from backend.app.services.credential_purge import unseal

    container = _container()
    purge = unseal(container.crypto(), sealed)
    if purge.user_id != user_id:
        raise ValueError("purge request does not match the job's user")
    return await container.credential_purge_service().purge(purge)


@app.task(
    name="revoke_google_grant",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(max_attempts=REVOKE_ATTEMPTS, wait=REVOKE_RETRY_SECONDS),
)
async def revoke_google_grant(sealed: str, form_id: str, action_id: str) -> str:
    """Revoke at Google the broad grant a Google Sheets action held before it
    was reconnected with ``drive.file`` (one attempt; retried hourly for two
    days, then failed and reported by the admin portal's integrity monitor).
    The local copy is already gone; ``sealed`` is the encrypted
    GrantRevocation."""
    from backend.app.services.sheets_grant_revocation import unseal

    container = _container()
    revocation = unseal(container.crypto(), sealed)
    if (revocation.form_id, revocation.action_id) != (form_id, action_id):
        raise ValueError("revocation request does not match the job's action")
    return await container.sheets_grant_service().revoke(revocation)


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


@app.periodic(cron="47 3 * * *", periodic_id="sso_release_retry")
@app.task(
    name="sso_release_retry",
    queue=DEFAULT_QUEUE,
    queueing_lock="sso_release_retry",
)
async def sso_release_retry(timestamp: int) -> str:
    """Daily: delete in Polis the SSO connections of deleted workspaces that
    a failed Polis call left behind, so they never keep holding an identity
    provider's entity ID (docs/sso.md). ``python -m backend.sso
    release-pending`` does the same by hand."""
    result = await _container().sso_connection_service().retry_pending_releases()
    return f"{result['released']} released, {result['failed']} failed"


DOMAIN_RECHECK_BATCH = 100
DOMAIN_RECHECK_MAX_BATCHES = 20


@app.periodic(cron="23 * * * *", periodic_id="recheck_verified_domains")
@app.task(
    name="recheck_verified_domains",
    queue=DEFAULT_QUEUE,
    queueing_lock="recheck_verified_domains",
)
async def recheck_verified_domains(timestamp: int) -> str:
    """Re-check the TXT record of every verified email domain once its
    ``VERIFIED_DOMAINS_RECHECK_INTERVAL_HOURS`` (24) have passed
    (docs/verified-domains.md). Runs hourly so each domain is checked about
    a day after the last check, not up to two; at most
    ``DOMAIN_RECHECK_MAX_BATCHES`` batches per run (the rest wait an hour).
    Logs and returns counts only."""
    from loguru import logger

    service = _container().workspace_domain_service()
    totals = {"checked": 0, "passed": 0, "failed": 0, "lost": 0}
    for _ in range(DOMAIN_RECHECK_MAX_BATCHES):
        counts = await service.recheck_verified_domains(limit=DOMAIN_RECHECK_BATCH)
        for key in totals:
            totals[key] += counts.get(key, 0)
        if counts.get("checked", 0) < DOMAIN_RECHECK_BATCH:
            break
    logger.info("verified domains re-checked: {}", totals)
    return ", ".join(f"{totals[k]} {k}" for k in totals)


def run_action_deferrer(queueing_lock: str):
    """Defer ``run_action`` to the actions queue without importing its body."""
    return app.configure_task(
        name=RUN_ACTION, queue=ACTIONS_QUEUE, queueing_lock=queueing_lock
    )
