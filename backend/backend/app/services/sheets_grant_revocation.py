"""After re-consent: store the new ``drive.file`` grant, then revoke the old
broad one at Google (docs/RUNNING_INTEGRATIONS.md).

While the backend runs the Sheets flow (``GOOGLE_SHEETS_OAUTH=backend``), the
OAuth callback stores the new credential through :meth:`SheetsGrantService.store_new_grant`:

1. **One write** replaces the action's credential and clears the re-consent
   markers (``needs_reconsent``, ``reconsent_skipped_runs``,
   ``reconsent_mailed_at``); published versions' copies of the credential are
   replaced too, so the old ciphertext is gone locally whatever happens next.
2. When the credential it replaced was **legacy** (``scopes`` other than
   exactly ``drive.file``), its refresh token is revoked at Google:
   ``POST https://oauth2.googleapis.com/revoke`` with a form-encoded
   ``token``. The address is pinned here, never read from the credential or
   from settings. Google answers 200 when revoked and 400 ``invalid_token``
   when the token is already revoked or expired: both count as done.
3. A revocation that fails never blocks the new grant: a retryable
   ``revoke_google_grant`` job is queued (procrastinate,
   ``JOBS_BACKEND__revoke_google_grant=postgres``), one attempt an hour for
   two days. Its argument is the token sealed with the backend's Fernet key.
   A job still pending a day later, or failed, is reported by the admin
   portal's integrity monitor (``admin.credential_purges_overdue()``). When it
   cannot be queued (Temporal routing, no queue), that is logged with ids.

Google's revocation removes the user's whole grant to the OAuth client that
issued the token. A legacy credential issued to the **same** client as the
new grant (the Google Forms service configured with the sign-in client) is
therefore not revoked: that would revoke the new ``drive.file`` grant with it.
It is deleted locally all the same and logged as ``same_client``.

Under ``google_service`` nothing here runs: the callback stores the credential
as before. Logs carry form and action ids, outcomes and counts only, never a
token.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from http import HTTPStatus
from typing import Optional

import httpx
from common.configs.crypto import Crypto
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.sheets_reconsent import (
    MAILED_AT,
    NEEDS_RECONSENT,
    SKIPPED_RUNS,
    is_legacy_scopes,
)
from backend.config import settings

# Pinned: never a stored or configured address.
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
REVOKE_JOB = "revoke_google_grant"
REVOKE_TIMEOUT_SECONDS = 20
# the job: one attempt an hour for two days, then it fails (and stays visible)
REVOKE_ATTEMPTS = 48
REVOKE_RETRY_SECONDS = 3600
RECONSENT_MARKERS = [NEEDS_RECONSENT, SKIPPED_RUNS, MAILED_AT]

MESSAGE_FORM_NOT_FOUND = "Form not found"


@dataclass(frozen=True)
class GrantRevocation:
    form_id: str
    action_id: str
    token: str


class GrantRevocationFailed(Exception):
    """This attempt did not revoke the grant; the job retries. The message
    holds an HTTP status or an error class, never the token."""


def seal(crypto: Crypto, revocation: GrantRevocation) -> str:
    return crypto.encrypt(json.dumps(asdict(revocation)))


def unseal(crypto: Crypto, sealed: str) -> GrantRevocation:
    return GrantRevocation(**json.loads(crypto.decrypt(sealed)))


def _error_code(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return "unknown"
    return error if isinstance(error, str) and error.isidentifier() else "unknown"


async def revoke_at_google(
    token: str, transport: Optional[httpx.AsyncBaseTransport] = None
) -> str:
    """One revocation attempt: ``"revoked"`` or ``"already_invalid"`` (done
    either way); raises :class:`GrantRevocationFailed` otherwise."""
    try:
        async with httpx.AsyncClient(
            transport=transport, timeout=REVOKE_TIMEOUT_SECONDS
        ) as client:
            response = await client.post(
                REVOKE_URL,
                data={"token": token},
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as error:
        raise GrantRevocationFailed(type(error).__name__) from None
    if response.status_code == HTTPStatus.OK:
        return "revoked"
    error = _error_code(response)
    if response.status_code == HTTPStatus.BAD_REQUEST and error == "invalid_token":
        return "already_invalid"
    raise GrantRevocationFailed(f"status={response.status_code} error={error}")


def token_to_revoke(previous: Optional[str], crypto: Crypto) -> tuple:
    """``(token, reason)`` for the credential a new grant replaced: the token
    to revoke (its refresh token, else its access token) or ``None`` with the
    reason it is left alone."""
    if not previous:
        return None, "no_previous"
    try:
        credential = json.loads(crypto.decrypt(previous))
    except Exception:  # noqa: BLE001 — undecryptable or not JSON
        return None, "unreadable"
    if not isinstance(credential, dict):
        return None, "unreadable"
    if not is_legacy_scopes(credential):
        return None, "not_legacy"
    client_id = credential.get("client_id")
    if not client_id or client_id == settings.google_sheets.CLIENT_ID:
        # revoking would revoke the user's whole grant to the sign-in
        # client, the new drive.file grant included
        return None, "same_client"
    token = credential.get("refresh_token") or credential.get("token")
    if not isinstance(token, str) or not token:
        return None, "no_token"
    return token, "legacy"


class SheetsGrantService:
    def __init__(self, form_repo, crypto: Crypto, temporal_service):
        self._form_repo = form_repo
        self._crypto = crypto
        self._jobs = temporal_service
        # tests replace it with a fake Google
        self.transport: Optional[httpx.AsyncBaseTransport] = None

    async def store_new_grant(self, form_id: str, action_id: str, credential: str) -> str:
        """Store the new credential (clearing the re-consent markers) and
        revoke the legacy grant it replaced. Returns the revocation outcome:
        ``revoked``, ``already_invalid``, ``queued``, ``not_queued`` or why
        nothing was revoked. Only a failed store raises."""
        result = await self._form_repo.replace_action_credential(
            str(form_id), str(action_id), credential, clear_parameters=RECONSENT_MARKERS
        )
        if not result or not result.get("stored"):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_FORM_NOT_FOUND)
        token, reason = token_to_revoke(result.get("previous"), self._crypto)
        if token is None:
            if reason not in ("no_previous", "not_legacy"):
                logger.info(
                    "sheets grant: old grant not revoked form={} action={} reason={}",
                    form_id,
                    action_id,
                    reason,
                )
            return reason
        return await self.revoke_or_queue(
            GrantRevocation(form_id=str(form_id), action_id=str(action_id), token=token)
        )

    async def revoke_or_queue(self, revocation: GrantRevocation) -> str:
        try:
            outcome = await revoke_at_google(revocation.token, self.transport)
        except GrantRevocationFailed as failure:
            logger.warning(
                "sheets grant: revocation failed form={} action={} ({}); queuing a retry",
                revocation.form_id,
                revocation.action_id,
                failure,
            )
        else:
            logger.info(
                "sheets grant: old grant {} form={} action={}",
                outcome,
                revocation.form_id,
                revocation.action_id,
            )
            return outcome
        try:
            return await self._jobs.queue_grant_revocation(revocation)
        except Exception as exc:  # noqa: BLE001 — never blocks the new grant
            logger.error(
                "sheets grant: revocation retry not queued form={} action={} ({})",
                revocation.form_id,
                revocation.action_id,
                type(exc).__name__,
            )
            return "not_queued"

    async def revoke(self, revocation: GrantRevocation) -> str:
        """The job body: one attempt. Raises GrantRevocationFailed to retry."""
        outcome = await revoke_at_google(revocation.token, self.transport)
        logger.info(
            "sheets grant: old grant {} by the retry job form={} action={}",
            outcome,
            revocation.form_id,
            revocation.action_id,
        )
        return outcome
