"""Mails about a change to an account's second factor (docs/totp.md).

The auth service owns the wording and finds the address from the account id:
this sends only an id, a kind and a few counts, in the background, never on the
path of the request that caused it, once, without retries (a notice is a courtesy
about something already done). A failure is logged without the address."""

import asyncio
from typing import Optional, Set

from loguru import logger

from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.request_context import current_request
from backend.config import settings

NOTIFY_PATH = "/notifications/security"
NOTIFY_TIMEOUT_SECONDS = 10
LOCALE_MAX = 35

ENROLLED = "enrolled"
REMOVED = "removed"
RECOVERY_USED = "recovery_used"
LOCKED = "locked"
RESET = "reset"
RESET_OWNER = "reset_owner"


def request_locale() -> Optional[str]:
    """The language of the request that caused the notice (its first
    Accept-Language tag), when there is one."""
    context = current_request()
    if context is None:
        return None
    for name, value in context.scope.get("headers") or []:
        if name == b"accept-language":
            first = value.decode("latin-1").split(",")[0].split(";")[0].strip()
            return first[:LOCALE_MAX] or None
    return None


class MfaNotifier:
    def __init__(self, http_client):
        self._http_client = http_client
        self._tasks: Set[asyncio.Task] = set()

    def notify(
        self,
        user_id,
        kind: str,
        *,
        recovery_left: Optional[int] = None,
        minutes: Optional[int] = None,
        workspace_title: Optional[str] = None,
    ) -> None:
        notice = {"user_id": str(user_id), "kind": kind}
        if recovery_left is not None:
            notice["recovery_left"] = int(recovery_left)
        if minutes is not None:
            notice["minutes"] = int(minutes)
        if workspace_title:
            notice["workspace_title"] = str(workspace_title)[:1000]
        locale = request_locale()
        if locale:
            notice["locale"] = locale
        try:
            task = asyncio.get_running_loop().create_task(self._send(notice))
        except RuntimeError:  # no loop: nothing to send from
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _send(self, notice: dict) -> None:
        try:
            await self._http_client.post(
                settings.auth_settings.BASE_URL + NOTIFY_PATH,
                json=notice,
                headers=auth_service_headers(),
                timeout=NOTIFY_TIMEOUT_SECONDS,
            )
        except Exception as error:  # noqa: BLE001 — never reaches the request
            logger.warning(
                "second-factor notice not sent kind={} ({})",
                notice.get("kind"),
                type(error).__name__,
            )

    async def flush(self) -> None:
        """Wait for the notices in flight (shutdown and tests)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
