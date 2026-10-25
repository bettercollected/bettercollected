"""Google Sheets credentials granted before the ``drive.file`` flow: re-consent
on next use, never kept silently (docs/RUNNING_INTEGRATIONS.md).

A stored Sheets credential is **legacy** unless its ``scopes`` (a
space-separated string, as the actions executor reads it) is exactly
``drive.file``: the Google Forms service's flow granted ``spreadsheets`` and
full ``drive`` access. While the backend runs the Sheets flow
(``GOOGLE_SHEETS_OAUTH=backend``), the next use of an action holding one (a
submission that would run it, or opening it in the builder):

* marks the action ``needs_reconsent`` (a parameter on the form's action, no
  migration) and, for a submission, skips the run and counts it
  (``reconsent_skipped_runs``), so nothing is written with the broad grant;
* mails the workspace's billing owner once per action ("Reconnect Google
  Sheets", a link to the form's integrations), through the auth service, in
  a task of its own: the submission never waits for it. The
  ``reconsent_mailed_at`` marker is claimed before the mail. A refusal that
  can never succeed (422: a handle or setting auth cannot build a link from)
  keeps it and is logged once; a transient failure (auth unreachable, 5xx)
  is retried a few times, then the marker is released so a later use tries
  again. Auth's 429 (its hourly cap per owner) and a task cancelled at
  shutdown release it at once.

Saving the action in the builder with a legacy grant is refused (409
``sheets_reconsent_required``): the user reconnects first.

Under ``google_service`` nothing is enforced: reconnecting there grants the
broad scopes again, so a skipped action could never run again. Reconnecting
under ``backend`` stores the new grant and clears the markers in one write,
then revokes the old grant at Google (services/sheets_grant_revocation.py).
Logs carry ids and counts only.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from http import HTTPStatus
from typing import Any, Optional

import httpx

from common.configs.crypto import Crypto
from common.services.http_client import HttpClient
from loguru import logger

from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.services.google_sheets_oauth import DRIVE_FILE_SCOPE
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings

SHEETS_ACTION = FormIntegrationType.GOOGLE_SHEET  # "integrate_google_sheets"
CREDENTIALS = "Credentials"
NEEDS_RECONSENT = "needs_reconsent"
SKIPPED_RUNS = "reconsent_skipped_runs"
MAILED_AT = "reconsent_mailed_at"
# The auth service sends the mail (its templates and SMTP settings).
NOTIFY_PATH = "/notifications/sheets-reconnect"
NOTIFY_TIMEOUT_SECONDS = 5
# Waits before each retry of a transient failure; after the last one the
# marker is released and a later use of the action tries again.
NOTIFY_RETRY_DELAYS_S = (5, 30, 120)
# How long shutdown waits for mails in flight before cancelling them.
SHUTDOWN_GRACE_SECONDS = 5
# The auth service's limits (SheetsReconnectNotice): titles are clipped,
# an over-long locale is left out (the mail falls back to English).
TITLE_MAX_LENGTH = 1000
LOCALE_MAX_LENGTH = 35
# The builder's answer when an action with a legacy grant is saved.
RECONSENT_REQUIRED_CODE = "sheets_reconsent_required"


def reconsent_enforced() -> bool:
    """Legacy credentials are held back only once the backend runs the
    ``drive.file`` flow, so a reconnect yields a credential that runs."""
    return settings.google_sheets.SHEETS_OAUTH == "backend"


def credential_scopes(credential: Any) -> list:
    """The scopes a decrypted credential records (string or list alike)."""
    scopes = credential.get("scopes") if isinstance(credential, dict) else None
    if isinstance(scopes, str):
        return scopes.split()
    if isinstance(scopes, (list, tuple)):
        return [str(scope) for scope in scopes]
    return []


def is_legacy_scopes(credential: Any) -> bool:
    return credential_scopes(credential) != [DRIVE_FILE_SCOPE]


def stored_credential(form: Any, action_id: Any) -> Optional[str]:
    """The action's encrypted ``Credentials`` secret on ``form``, if any."""
    secrets = getattr(form, "secrets", None) or {}
    for secret in secrets.get(str(action_id)) or []:
        if getattr(secret, "name", None) == CREDENTIALS and getattr(
            secret, "value", None
        ):
            return secret.value
    return None


def is_legacy_credential(encrypted: Optional[str], crypto: Crypto) -> Optional[bool]:
    """``None`` without a credential (not connected: nothing to hold back);
    otherwise whether it is legacy. One that cannot be read counts as legacy:
    it cannot run either, and reconnecting replaces it."""
    if not encrypted:
        return None
    try:
        credential = json.loads(crypto.decrypt(encrypted))
    except Exception:  # noqa: BLE001 — undecryptable or not JSON
        return True
    return is_legacy_scopes(credential)


def clip(value: Optional[str], limit: int = TITLE_MAX_LENGTH) -> Optional[str]:
    """``value`` cut to ``limit`` characters (the last one an ellipsis)."""
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


def notice_failure(exc: BaseException) -> str:
    """How a failed notice is handled: ``final`` (422: auth can never send
    it), ``transient`` (unreachable, timeout, 5xx: retried) or ``other``
    (released, a later use tries again). A 429 is auth's hourly cap per
    owner: a retry within minutes cannot pass it, so it is ``other``."""
    if isinstance(exc, (httpx.TransportError, TimeoutError)):
        return "transient"
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        return "other"
    if status == HTTPStatus.UNPROCESSABLE_ENTITY:
        return "final"
    if status >= 500:
        return "transient"
    return "other"


def parameter(form: Any, action_id: Any, name: str) -> Optional[str]:
    parameters = getattr(form, "parameters", None) or {}
    for value in parameters.get(str(action_id)) or []:
        if getattr(value, "name", None) == name:
            return value.value
    return None


class SheetsReconsentService:
    def __init__(
        self,
        form_repo,
        workspace_repo,
        crypto: Crypto,
        http_client: HttpClient,
    ):
        self._form_repo = form_repo
        self._workspace_repo = workspace_repo
        self._crypto = crypto
        self._http_client = http_client
        self.retry_delays_s = NOTIFY_RETRY_DELAYS_S
        # notices in flight; held so they are not collected mid-run
        self._pending: set[asyncio.Task] = set()

    def is_legacy(self, form: Any, action_id: Any) -> bool:
        return bool(
            is_legacy_credential(stored_credential(form, action_id), self._crypto)
        )

    async def hold_back_run(
        self, form: Any, action: Any, workspace_id: Any
    ) -> bool:
        """True when this submission's run of ``action`` must not be
        dispatched: a Sheets action holding a legacy credential while the
        rule is enforced. Marks the action, counts the skipped run and starts
        the one-time mail (in the background)."""
        if getattr(action, "name", None) != SHEETS_ACTION or not reconsent_enforced():
            return False
        if not self.is_legacy(form, action.id):
            return False
        await self._mark(form, action.id, workspace_id, skipped_run=True)
        return True

    async def check_in_builder(
        self, form: Any, action: Any, workspace_id: Any
    ) -> bool:
        """Opening the action in the builder: whether it needs reconnecting
        (marked, and the owner mailed once, as on a submission)."""
        if getattr(action, "name", None) != SHEETS_ACTION or not reconsent_enforced():
            return False
        if not self.is_legacy(form, action.id):
            return False
        await self._mark(form, action.id, workspace_id, skipped_run=False)
        return True

    async def _mark(
        self, form: Any, action_id: Any, workspace_id: Any, skipped_run: bool
    ) -> None:
        form_id = str(form.form_id)
        try:
            await self._form_repo.update_action_parameters(
                form_id,
                str(action_id),
                values={NEEDS_RECONSENT: "true"},
                increment=SKIPPED_RUNS if skipped_run else None,
            )
        except Exception as exc:  # noqa: BLE001 — the run stays skipped
            logger.warning(
                "sheets reconsent: marking failed form={} action={} ({})",
                form_id,
                action_id,
                type(exc).__name__,
            )
        logger.info(
            "sheets reconsent: legacy credential form={} action={} workspace={} "
            "skipped_run={}",
            form_id,
            action_id,
            workspace_id,
            skipped_run,
        )
        self._notify_in_background(form, action_id, workspace_id)

    def _notify_in_background(
        self, form: Any, action_id: Any, workspace_id: Any
    ) -> None:
        """Mail the billing owner in a task of its own, never on the
        submission's request path. Nothing to do when the form already
        carries the marker (mailed, or a mail that can never be sent)."""
        if parameter(form, action_id, MAILED_AT):
            return
        language = getattr(getattr(form, "settings", None), "language", None)
        task = asyncio.create_task(
            self._mail_once(
                form_id=str(form.form_id),
                form_title=getattr(form, "title", None),
                language=language,
                action_id=str(action_id),
                workspace_id=workspace_id,
            )
        )
        self._pending.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task) -> None:
        self._pending.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.warning(
                "sheets reconsent: notice task ended with {}",
                type(task.exception()).__name__,
            )

    async def drain(self) -> None:
        """Wait for the notices in flight (tests)."""
        while self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)

    async def shutdown(self, timeout: float = SHUTDOWN_GRACE_SECONDS) -> None:
        """At shutdown, before the stores close: let the notices in flight
        finish for up to ``timeout`` seconds, then cancel the rest (each
        releases its marker, so a later use mails again)."""
        pending = list(self._pending)
        if not pending:
            return
        _, unfinished = await asyncio.wait(pending, timeout=timeout)
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
            logger.info(
                "sheets reconsent: {} mail(s) interrupted at shutdown", len(unfinished)
            )

    async def _mail_once(
        self,
        form_id: str,
        form_title: Optional[str],
        language: Optional[str],
        action_id: str,
        workspace_id: Any,
    ) -> str:
        """Claim the ``reconsent_mailed_at`` marker, then ask the auth service
        to mail the billing owner. Returns ``sent``, ``claimed`` (someone
        else holds the marker), ``final`` (marker kept) or ``released``."""
        ids = f"form={form_id} action={action_id} workspace={workspace_id}"
        try:
            claimed = await self._form_repo.update_action_parameters(
                form_id,
                action_id,
                values={MAILED_AT: dt.datetime.now(dt.timezone.utc).isoformat()},
                only_if_absent=MAILED_AT,
            )
        except Exception as exc:  # noqa: BLE001 — a later use tries again
            logger.warning(
                "sheets reconsent: mail marker failed {} ({})", ids, type(exc).__name__
            )
            return "released"
        if not claimed:
            return "claimed"
        try:
            return await self._send_claimed(
                form_id, form_title, language, action_id, workspace_id, ids
            )
        except asyncio.CancelledError:
            # stopped mid-way (shutdown, often during a retry wait): free the
            # marker so a later use sends the mail, then stop
            await self._release(form_id, action_id)
            logger.info("sheets reconsent: mail interrupted, marker released {}", ids)
            raise

    async def _send_claimed(
        self,
        form_id: str,
        form_title: Optional[str],
        language: Optional[str],
        action_id: str,
        workspace_id: Any,
        ids: str,
    ) -> str:
        """The mail, once this task holds the marker."""
        try:
            workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sheets reconsent: mail not sent {} ({})", ids, type(exc).__name__
            )
            return await self._release(form_id, action_id)
        if workspace is None or not getattr(workspace, "owner_id", None):
            # nobody to mail, and no retry would change that
            logger.warning("sheets reconsent: mail not sent, no billing owner {}", ids)
            return "final"
        notice = {
            "user_id": str(workspace.owner_id),
            "workspace_name": workspace.workspace_name,
            "workspace_title": clip(workspace.title),
            "form_id": form_id,
            "form_title": clip(form_title),
        }
        if language and len(language) <= LOCALE_MAX_LENGTH:
            notice["locale"] = language
        delays = list(self.retry_delays_s)
        while True:
            try:
                await self._http_client.post(
                    settings.auth_settings.BASE_URL + NOTIFY_PATH,
                    json=notice,
                    headers=auth_service_headers(),
                    timeout=NOTIFY_TIMEOUT_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001 — never reaches a respondent
                kind = notice_failure(exc)
                if kind == "final":
                    # auth refuses this notice for good: keep the marker, so
                    # it is neither retried nor logged again
                    logger.warning(
                        "sheets reconsent: mail refused by auth (422), not retried {}",
                        ids,
                    )
                    return "final"
                if kind == "transient" and delays:
                    await asyncio.sleep(delays.pop(0))
                    continue
                logger.warning(
                    "sheets reconsent: mail not sent {} ({})", ids, type(exc).__name__
                )
                return await self._release(form_id, action_id)
            logger.info("sheets reconsent: owner mailed {}", ids)
            return "sent"

    async def _release(self, form_id: str, action_id: str) -> str:
        try:
            await self._form_repo.update_action_parameters(
                form_id, action_id, remove=[MAILED_AT]
            )
        except Exception:  # noqa: BLE001
            pass
        return "released"


async def count_legacy_sheets_actions(form_repo, action_repo, crypto: Crypto) -> dict:
    """Read-only operator count: Sheets actions on forms, by credential state.
    Counts only, never ids, titles or tokens."""
    actions = await action_repo.get_all_actions()
    sheets_ids = [str(a.id) for a in actions if a.name == SHEETS_ACTION]
    forms = await form_repo.get_forms_with_action_secrets(sheets_ids)
    counts = {
        "sheets_actions_with_credential": 0,
        "legacy": 0,
        "drive_file": 0,
        "unreadable": 0,
        "needs_reconsent_marked": 0,
        "owners_mailed": 0,
        "skipped_runs": 0,
        "forms": 0,
    }
    for form in forms:
        seen = False
        for action_id in sheets_ids:
            encrypted = stored_credential(form, action_id)
            if not encrypted:
                continue
            seen = True
            counts["sheets_actions_with_credential"] += 1
            try:
                credential = json.loads(crypto.decrypt(encrypted))
            except Exception:  # noqa: BLE001
                counts["unreadable"] += 1
                counts["legacy"] += 1
                credential = None
            if credential is not None:
                if is_legacy_scopes(credential):
                    counts["legacy"] += 1
                else:
                    counts["drive_file"] += 1
            if parameter(form, action_id, NEEDS_RECONSENT) == "true":
                counts["needs_reconsent_marked"] += 1
            if parameter(form, action_id, MAILED_AT):
                counts["owners_mailed"] += 1
            try:
                counts["skipped_runs"] += int(
                    parameter(form, action_id, SKIPPED_RUNS) or 0
                )
            except ValueError:
                pass
        counts["forms"] += int(seen)
    return counts
