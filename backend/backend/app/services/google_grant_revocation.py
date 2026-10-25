"""Revoking a Google grant, for the queued ``revoke_google_grant`` jobs that
release 4.1 leaves behind.

Release 4.1 replaces the broad grant a Google Sheets action held with a
narrower one and queues a retryable revocation of the old grant when Google
could not be reached at that moment. This release has no re-consent flow of its
own, but a stack rolled back from 4.1 can still hold such rows, and the grant
is the user's to have revoked: the body is the same single call, repeated until
Google answers.

``POST https://oauth2.googleapis.com/revoke`` with the token form-encoded. The
address is pinned here, never read from the job, from a credential or from
settings. Google answers 200 when revoked and 400 ``invalid_token`` when the
token is already revoked or expired; both are done, so the job is idempotent.

The job's ``sealed`` argument is the encrypted ``GrantRevocation`` (the token
travels encrypted). Logs carry form and action ids and outcomes only, never the
token and never an exception text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Optional

import httpx
from common.configs.crypto import Crypto
from loguru import logger

# Pinned: never a stored or configured address.
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
REVOKE_TIMEOUT_SECONDS = 20
# one attempt an hour for two days, as on 4.1, then the job fails and stays visible
REVOKE_ATTEMPTS = 48
REVOKE_RETRY_SECONDS = 3600


@dataclass(frozen=True)
class GrantRevocation:
    form_id: str
    action_id: str
    token: str


class GrantRevocationFailed(Exception):
    """This attempt did not revoke the grant; the job retries. The text holds
    an HTTP status or an error class, never the token."""


def unseal(crypto: Crypto, sealed: str) -> GrantRevocation:
    data = json.loads(crypto.decrypt(sealed))
    return GrantRevocation(
        form_id=data["form_id"], action_id=data["action_id"], token=data["token"]
    )


def _error_code(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return "unknown"
    return error if isinstance(error, str) and error.isidentifier() else "unknown"


class GoogleGrantService:
    def __init__(self):
        # tests replace it with a fake Google
        self.transport: Optional[httpx.AsyncBaseTransport] = None

    async def revoke(self, revocation: GrantRevocation) -> str:
        """The job body: one attempt; ``"revoked"`` or ``"already_invalid"``
        (done either way). Raises GrantRevocationFailed to retry."""
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=REVOKE_TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    REVOKE_URL,
                    data={"token": revocation.token},
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as error:
            raise GrantRevocationFailed(type(error).__name__) from None
        if response.status_code == HTTPStatus.OK:
            outcome = "revoked"
        else:
            error = _error_code(response)
            if (
                response.status_code == HTTPStatus.BAD_REQUEST
                and error == "invalid_token"
            ):
                outcome = "already_invalid"
            else:
                raise GrantRevocationFailed(
                    f"status={response.status_code} error={error}"
                ) from None
        logger.info(
            "google grant: old grant {} form={} action={}",
            outcome,
            revocation.form_id,
            revocation.action_id,
        )
        return outcome
