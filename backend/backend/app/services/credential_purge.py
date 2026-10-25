"""Erasing a deleted account's stored provider credentials.

Account deletion (``AuthService.delete_user``) erases the account, its
sessions and its workspace data first; the user's stored OAuth credentials on
a provider service (Google Forms) come last and never hold that back:

1. the provider service deletes them (``DELETE /{provider}/oauth/credentials``;
   for Google it revokes the grant at Google first, in ``on`` and ``readonly``);
2. when that fails, or in ``GOOGLE_FORMS_IMPORT=off`` (nothing calls the
   service), a retryable ``purge_provider_credentials`` job is queued
   (``JOBS_BACKEND__purge_provider_credentials=postgres``, procrastinate). Only
   the queuing is retried in the deletion itself; if it still can't be queued
   the deletion job fails after the erasure, so it is retried and shows up as a
   failed or overdue job (``CredentialPurgeNotQueued``).

The job (``backend/jobs/tasks.py``) retries for two days: through the
service in ``on``/``readonly`` (so the grant is revoked), and in ``off``
through ``google.purge_user_credentials(user_id, email)`` (google revision
0005), the only access the backend's role has to the Google schema — when the
Google group is on Postgres only. Mongo and dual stacks rely on the service.
A purge that is still pending after a day, or failed, is reported by the admin
portal's integrity monitor (``admin.credential_purges_overdue()``).

The job's arguments carry the user id and, encrypted, the email: finished job
rows are kept by the queue. Logs name ids and statuses only.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from http import HTTPStatus
from typing import Optional

import aiohttp
from sqlalchemy import text

from common.db.flags import FlagError, WriteMode, load_flags

from backend.app.exceptions import HTTPException
from backend.app.services.google_forms_mode import google_service_enabled, is_google
from backend.app.utils import AiohttpClient

log = logging.getLogger(__name__)

PURGE_JOB = "purge_provider_credentials"
# seconds a provider service gets to delete a user's stored credentials
CREDENTIALS_DELETE_TIMEOUT = 20
# queuing attempts inside the deletion, and the pause before each retry
QUEUE_ATTEMPTS = 3
QUEUE_RETRY_SECONDS = 1.0
# the job: one attempt an hour for two days, then it fails (and stays visible)
PURGE_ATTEMPTS = 48
PURGE_RETRY_SECONDS = 3600


@dataclass(frozen=True)
class CredentialPurge:
    user_id: str
    email: str
    provider: str


class CredentialPurgeNotQueued(Exception):
    """The purge could not be queued; raised after the rest of the erasure."""


class CredentialPurgeFailed(Exception):
    """This attempt did not erase the credentials; the job retries."""


def seal(crypto, purge: CredentialPurge) -> str:
    return crypto.encrypt(json.dumps(asdict(purge)))


def unseal(crypto, sealed: str) -> CredentialPurge:
    return CredentialPurge(**json.loads(crypto.decrypt(sealed)))


def google_store_is_postgres_only(flags=None) -> bool:
    """Whether the Google Forms service keeps its data in Postgres only (its
    ``google`` group writes Postgres and nothing else)."""
    try:
        flags = flags or load_flags()
    except FlagError:  # an inconsistent setting is not "Postgres only"
        return False
    return flags.write_mode("google") is WriteMode.POSTGRES


class CredentialPurgeService:
    def __init__(self, form_provider_service, temporal_service, pg_engine=None):
        self._providers = form_provider_service
        self._jobs = temporal_service
        self._engine = pg_engine

    async def delete_via_service(self, purge: CredentialPurge) -> Optional[int]:
        """Ask the provider service to delete them; its HTTP status, or None
        when it could not be reached (or may not be called)."""
        try:
            url = await self._providers.get_provider_url(purge.provider)
            response = await AiohttpClient.get_aiohttp_client().delete(
                f"{url}/{purge.provider}/oauth/credentials",
                params={"user_id": purge.user_id, "email": purge.email},
                timeout=aiohttp.ClientTimeout(total=CREDENTIALS_DELETE_TIMEOUT),
            )
            return response.status
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, HTTPException):
            return None

    async def erase_or_queue(self, purge: CredentialPurge) -> str:
        """Part of the account deletion, after everything else: "deleted",
        "queued" or "already_queued". Raises CredentialPurgeNotQueued."""
        if not (is_google(purge.provider) and not google_service_enabled()):
            status = await self.delete_via_service(purge)
            if status == HTTPStatus.OK:
                return "deleted"
            log.warning(
                "Account deletion: credentials of user %s not deleted on the %s "
                "service (%s); queuing a purge",
                purge.user_id,
                purge.provider,
                status if status is not None else "unreachable",
            )
        last_error = None
        for attempt in range(QUEUE_ATTEMPTS):
            try:
                return await self._jobs.queue_credential_purge(purge)
            except Exception as exc:  # noqa: BLE001 - retried, then raised below
                last_error = type(exc).__name__
                if attempt + 1 < QUEUE_ATTEMPTS:
                    await asyncio.sleep(QUEUE_RETRY_SECONDS * (attempt + 1))
        log.error(
            "Account deletion: the credential purge of user %s (%s) could not be "
            "queued (%s)",
            purge.user_id,
            purge.provider,
            last_error,
        )
        raise CredentialPurgeNotQueued(purge.user_id)

    async def purge(self, purge: CredentialPurge) -> str:
        """The job body: one attempt. Raises CredentialPurgeFailed to retry."""
        if not (is_google(purge.provider) and not google_service_enabled()):
            status = await self.delete_via_service(purge)
            if status == HTTPStatus.OK:
                log.info("Credential purge: user %s on %s done", purge.user_id, purge.provider)
                return "deleted"
            raise CredentialPurgeFailed(
                f"{purge.provider} service answered "
                f"{status if status is not None else 'unreachable'}"
            )
        # GOOGLE_FORMS_IMPORT=off: no call to the service or to Google
        if self._engine is None or not google_store_is_postgres_only():
            raise CredentialPurgeFailed(
                "the Google Forms service is off and its store is not Postgres only"
            )
        async with self._engine.begin() as conn:
            deleted = (
                await conn.execute(
                    text("SELECT google.purge_user_credentials(:user_id, :email)"),
                    {"user_id": purge.user_id, "email": purge.email},
                )
            ).scalar()
        log.info(
            "Credential purge: user %s on google done in the database (%s rows)",
            purge.user_id,
            deleted,
        )
        return "deleted"
