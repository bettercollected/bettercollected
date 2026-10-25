"""Erasing a deleted account's stored provider credentials, for the queued
``purge_provider_credentials`` jobs that release 4.1 leaves behind.

Release 4.1 queues the job (procrastinate) when it could not erase a deleted
account's credentials at the provider service during the deletion; a stack
rolled back to this release can still hold such rows. The body is the same
erasure account deletion does here (``AuthService.delete_credentials_from_
integrations``): ``DELETE {provider service}/{provider}/oauth/credentials``,
which removes the user's rows by user id (and legacy rows by email). It is
idempotent: erasing what is already gone answers 200.

The job's ``sealed`` argument is the encrypted ``CredentialPurge`` (the email
travels encrypted, finished job rows are kept by the queue). Logs name user
ids and statuses only: never the email, and never an exception text, because an
HTTP client's message can carry the request URL.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from http import HTTPStatus

import aiohttp

from backend.app.exceptions import HTTPException
from backend.app.utils import AiohttpClient

log = logging.getLogger(__name__)

# one attempt an hour for two days, as on 4.1, then the job fails and stays visible
PURGE_ATTEMPTS = 48
PURGE_RETRY_SECONDS = 3600
# seconds the provider service gets to delete a user's stored credentials
CREDENTIALS_DELETE_TIMEOUT = 20
# answers that may pass on a later attempt; any other 4xx is a request the
# service will never accept, so the job fails at once instead of retrying
# a provider's name as stored in the provider records ("google", "typeform"): it
# becomes a path segment of the service's address, so nothing else is accepted
_PROVIDER_NAME = re.compile(r"^[a-z0-9_-]{1,40}$")
_TRANSIENT_CLIENT_ERRORS = (HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.TOO_MANY_REQUESTS)


@dataclass(frozen=True)
class CredentialPurge:
    user_id: str
    email: str
    provider: str


class CredentialPurgeFailed(Exception):
    """This attempt did not erase the credentials; the job retries. The text
    holds an HTTP status or a fixed phrase, never an address."""


class CredentialPurgeRejected(Exception):
    """The provider service refused the request itself (a 4xx that will not
    pass); the job fails without retrying."""


def unseal(crypto, sealed: str) -> CredentialPurge:
    """The request a 4.1 job carries. Raises when it cannot be read; the job
    then fails once (a malformed argument never becomes readable)."""
    data = json.loads(crypto.decrypt(sealed))
    return CredentialPurge(
        user_id=data["user_id"], email=data["email"], provider=data["provider"]
    )


class CredentialPurgeService:
    def __init__(self, form_provider_service):
        self._providers = form_provider_service

    async def purge(self, purge: CredentialPurge) -> str:
        """The job body: one attempt. Raises CredentialPurgeFailed to retry."""
        if not _PROVIDER_NAME.match(purge.provider or ""):
            raise CredentialPurgeRejected("not a provider name")
        try:
            url = await self._providers.get_provider_url(purge.provider)
            if not url:
                raise CredentialPurgeFailed("provider not configured")
            # (the provider service takes the address as a query parameter; the
            # same call account deletion makes)
            response = await AiohttpClient.get_aiohttp_client().delete(
                f"{url}/{purge.provider}/oauth/credentials",
                params={"user_id": purge.user_id, "email": purge.email},
                timeout=aiohttp.ClientTimeout(total=CREDENTIALS_DELETE_TIMEOUT),
            )
            status = response.status
        except CredentialPurgeFailed:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, HTTPException):
            raise CredentialPurgeFailed("provider service unreachable") from None
        except Exception:  # noqa: BLE001 - e.g. a provider record without a URL
            raise CredentialPurgeFailed("provider service not usable") from None
        if status == HTTPStatus.OK:
            log.info(
                "Credential purge: user %s on %s done", purge.user_id, purge.provider
            )
            return "deleted"
        if 400 <= status < 500 and status not in _TRANSIENT_CLIENT_ERRORS:
            log.error(
                "Credential purge: user %s on %s refused by the service (%s)",
                purge.user_id,
                purge.provider,
                status,
            )
            raise CredentialPurgeRejected(f"{purge.provider} service answered {status}")
        raise CredentialPurgeFailed(f"{purge.provider} service answered {status}")
