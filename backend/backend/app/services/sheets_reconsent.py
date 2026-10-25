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
  Sheets", a link to the form's integrations), through the auth service; the
  ``reconsent_mailed_at`` marker is claimed before the mail and released again
  when the mail could not be handed over, so the next use retries.

Under ``google_service`` nothing is enforced: reconnecting there grants the
broad scopes again, so a skipped action could never run again. Reconnecting
under ``backend`` stores the new grant and clears the markers in one write,
then revokes the old grant at Google (services/sheets_grant_revocation.py).
Logs carry ids and counts only.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

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

    def is_legacy(self, form: Any, action_id: Any) -> bool:
        return bool(
            is_legacy_credential(stored_credential(form, action_id), self._crypto)
        )

    async def hold_back_run(
        self, form: Any, action: Any, workspace_id: Any
    ) -> bool:
        """True when this submission's run of ``action`` must not be
        dispatched: a Sheets action holding a legacy credential while the
        rule is enforced. Marks the action, counts the skipped run and sends
        the one-time mail."""
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
        try:
            await self._mail_once(form, action_id, workspace_id)
        except Exception as exc:  # noqa: BLE001 — never fails the submission
            logger.warning(
                "sheets reconsent: mail marker failed form={} action={} ({})",
                form_id,
                action_id,
                type(exc).__name__,
            )

    async def _mail_once(self, form: Any, action_id: Any, workspace_id: Any) -> bool:
        """Claim the ``reconsent_mailed_at`` marker, then ask the auth service
        to mail the billing owner; releases the marker when that fails."""
        form_id = str(form.form_id)
        claimed = await self._form_repo.update_action_parameters(
            form_id,
            str(action_id),
            values={MAILED_AT: dt.datetime.now(dt.timezone.utc).isoformat()},
            only_if_absent=MAILED_AT,
        )
        if not claimed:
            return False
        try:
            workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
            if workspace is None or not getattr(workspace, "owner_id", None):
                raise ValueError("no billing owner")
            language = getattr(getattr(form, "settings", None), "language", None)
            await self._http_client.post(
                settings.auth_settings.BASE_URL + NOTIFY_PATH,
                json={
                    "user_id": str(workspace.owner_id),
                    "workspace_name": workspace.workspace_name,
                    "workspace_title": workspace.title or None,
                    "form_id": form_id,
                    "form_title": getattr(form, "title", None) or None,
                    **({"locale": language} if language else {}),
                },
                headers=auth_service_headers(),
                timeout=NOTIFY_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 — retried on the next use
            logger.warning(
                "sheets reconsent: mail not sent form={} action={} workspace={} ({})",
                form_id,
                action_id,
                workspace_id,
                type(exc).__name__,
            )
            try:
                await self._form_repo.update_action_parameters(
                    form_id, str(action_id), remove=[MAILED_AT]
                )
            except Exception:  # noqa: BLE001
                pass
            return False
        logger.info(
            "sheets reconsent: owner mailed form={} action={} workspace={}",
            form_id,
            action_id,
            workspace_id,
        )
        return True


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
