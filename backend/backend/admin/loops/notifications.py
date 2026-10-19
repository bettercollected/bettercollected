"""The notification sender: mails every admin about outbox rows.

Rows come from ``admin.notifications`` (written in the same transaction as the
change they announce). The mail text is fixed per notification kind and names
only the action, the setting or task, the version or run id and the requesting
admin; payload fields outside those, values, parameters and key material are
never read. A kind without a template is marked ``failed`` and never rendered.

A row is ``sent`` only when every current admin's mail was accepted by the
transport. Admins already served stay recorded (as a truncated digest) so a
retry mails only the rest. Failures back off and give up after
``MAX_ATTEMPTS``. Due times use the database clock, so the app host's clock
cannot hold a notice back. The sender spends at most ``max_per_minute`` mails a minute,
and writes one summary audit row (counts only) per batch.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import deque
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.loops.base import Loop
from backend.admin.loops.status import StatusBoard
from backend.admin.security.clock import Clock
from backend.admin.security.mailer import AdminMailer, Message, clean
from backend.admin.services import audit

log = logging.getLogger("backend.admin.loops")

BATCH = 10
MAX_ATTEMPTS = 5
SEND_TIMEOUT = 30.0
BACKOFF_BASE = 60  # seconds; doubles per attempt, capped at an hour
BACKOFF_CAP = 3600

_SETTING = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_WORD = re.compile(r"^[a-z][a-z0-9_.]{0,63}$")
_TASK = re.compile(r"^[a-z][a-z0-9_.]{0,63}$")
_UUID = re.compile(r"^[0-9a-fA-F-]{32,36}$")
_TIER = re.compile(r"^T[1-5]$")


class BadPayload(Exception):
    """The payload lacks a field the template needs, or it has the wrong shape."""


def _field(payload: Mapping[str, Any], name: str, pattern: "re.Pattern[str]") -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not pattern.match(value):
        raise BadPayload(name)
    return value


def _version(payload: Mapping[str, Any], name: str = "version") -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 10**9:
        raise BadPayload(name)
    return value


def _actor(payload: Mapping[str, Any]) -> str:
    value = payload.get("actor")
    if not isinstance(value, str) or not value.strip():
        raise BadPayload("actor")
    return clean(value)


_FOOTER = "\nIf this was not expected, review the admin audit log.\n"


def _settings_changed(p: Mapping[str, Any]) -> Message:
    body = (
        "A critical setting was changed in the admin portal.\n\n"
        f"Setting: {_field(p, 'setting', _SETTING)}\n"
        f"Action: {_field(p, 'action', _WORD)}\n"
        f"Version: {_version(p)}\n"
        f"Requested by: {_actor(p)}\n" + _FOOTER
    )
    return Message("Security notice: an admin setting was changed", body)


def _keyset_changed(p: Mapping[str, Any]) -> Message:
    body = (
        "The response encryption keyset was changed from the admin portal.\n\n"
        f"Action: {_field(p, 'action', _WORD)}\n"
        f"Version: {_version(p)}\n"
        f"Requested by: {_actor(p)}\n" + _FOOTER
    )
    return Message("Security notice: the encryption keyset was changed", body)


def _keyset_reencrypt(p: Mapping[str, Any]) -> Message:
    body = (
        "A re-encryption of stored responses was requested from the admin portal.\n\n"
        f"Run: {_field(p, 'run_id', _UUID)}\n"
        f"Requested by: {_actor(p)}\n" + _FOOTER
    )
    return Message("Security notice: a key re-encryption was requested", body)


def _task_run(p: Mapping[str, Any]) -> Message:
    body = (
        "An admin task run was started or changed state.\n\n"
        f"Task: {_field(p, 'task', _TASK)}\n"
        f"Run: {_field(p, 'run_id', _UUID)}\n"
        f"State: {_field(p, 'state', _WORD)}\n"
        f"Requested by: {_actor(p)}\n" + _FOOTER
    )
    return Message("Security notice: an admin task run changed state", body)


def _integrity(p: Mapping[str, Any]) -> Message:
    problems = p.get("problems")
    count = _version(p, "count")
    if not isinstance(problems, list) or len(problems) > 20:
        raise BadPayload("problems")
    lines = []
    for item in problems:
        if not isinstance(item, dict):
            raise BadPayload("problems")
        key = item.get("key")
        reason = item.get("reason")
        if key != "*" and not (isinstance(key, str) and _SETTING.match(key)):
            raise BadPayload("problems")
        if not isinstance(reason, str) or not re.match(r"^[a-z][a-z0-9_]{0,31}$", reason):
            raise BadPayload("problems")
        lines.append(f"  {'settings manifest' if key == '*' else key}: {reason}")
    more = f"\n  and {count - len(lines)} more" if count > len(lines) else ""
    body = (
        f"The settings integrity check found {count} problem(s).\n\n"
        + "\n".join(lines)
        + more
        + "\n\nThe settings store may have been changed outside the portal. "
        "Review the admin audit log and the settings page.\n"
    )
    return Message("Security notice: the settings integrity check found a problem", body)


TEMPLATES: Dict[str, Callable[[Mapping[str, Any]], Message]] = {
    "settings.changed": _settings_changed,
    "settings.keyset_changed": _keyset_changed,
    "settings.keyset_reencrypt": _keyset_reencrypt,
    "tasks.run": _task_run,
    "settings.integrity": _integrity,
}


def render(kind: str, payload: Any) -> Message:
    """The mail for one row. Raises ``KeyError`` for an unknown kind and
    :class:`BadPayload` for a payload that does not fit its template."""
    template = TEMPLATES[kind]
    if not isinstance(payload, dict):
        raise BadPayload("payload")
    return template(payload)


def recipient_digest(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode()).hexdigest()[:16]


class NotificationSender(Loop):
    name = "notifications"
    lock_number = 1

    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        mailer: AdminMailer,
        admins: Callable[[], Sequence[str]],
        board: Optional[StatusBoard] = None,
        *,
        interval: float = 15.0,
        max_per_minute: int = 30,
        max_attempts: int = MAX_ATTEMPTS,
        batch: int = BATCH,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._mailer = mailer
        self._admins = admins
        self._board = board
        self.interval = interval
        self._max_per_minute = max_per_minute
        self._max_attempts = max_attempts
        self._batch = batch
        self._sent_at: "deque[float]" = deque()

    # --------------------------------------------------------- rate limit

    def _budget(self) -> int:
        now = self._clock.time()
        while self._sent_at and now - self._sent_at[0] >= 60:
            self._sent_at.popleft()
        return max(0, self._max_per_minute - len(self._sent_at))

    def _spent(self) -> None:
        self._sent_at.append(self._clock.time())

    # ------------------------------------------------------------- the pass

    async def run_once(self) -> str:
        await self._mailer.refresh_settings()  # saved admin mail settings, at most once a minute
        if not self._mailer.is_configured():
            if self._board is not None:
                self._board.mail = "mail not configured"
            return "idle: mail not configured"
        if self._board is not None:
            self._board.mail = "ok"
        admins = sorted({a.strip().lower() for a in self._admins() if a and a.strip()})
        if not admins:
            return "idle: no admins"
        if self._budget() == 0:
            return "idle: rate limited"

        counts = {"sent": 0, "retried": 0, "failed": 0, "mails": 0}
        async with self._engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, kind, payload, attempts, delivered_to "
                        "FROM admin.notifications "
                        "WHERE status = 'pending' AND next_attempt_at <= now() "
                        "ORDER BY created_at LIMIT :n FOR UPDATE SKIP LOCKED"
                    ),
                    {"n": self._batch},
                )
            ).all()
            for row in rows:
                if self._budget() == 0:
                    break
                await self._one(conn, row, admins, counts)
        if not rows:
            return "idle: nothing pending"
        await self._summarise(counts)
        return (
            f"sent {counts['sent']}, retry {counts['retried']}, "
            f"failed {counts['failed']}, mails {counts['mails']}"
        )

    async def _one(self, conn, row, admins, counts) -> None:
        try:
            message = render(row.kind, row.payload)
        except (KeyError, BadPayload) as exc:
            code = "unknown_kind" if isinstance(exc, KeyError) else "bad_payload"
            await self._finish(conn, row.id, "failed", code, row.attempts)
            counts["failed"] += 1
            return

        served = set(row.delivered_to or [])
        failed_any = False
        rate_stopped = False
        for address in admins:
            digest = recipient_digest(address)
            if digest in served:
                continue
            if self._budget() == 0:
                rate_stopped = True  # not a failure: the rest goes next pass
                break
            try:
                ok = await asyncio.wait_for(
                    self._mailer.send_message(address, message), SEND_TIMEOUT
                )
            except Exception:  # noqa: BLE001 - never log the cause (addresses)
                ok = False
            if ok:
                served.add(digest)
                counts["mails"] += 1
                self._spent()
            else:
                failed_any = True
        if not failed_any and not rate_stopped:
            await conn.execute(
                text(
                    "UPDATE admin.notifications SET status = 'sent', sent_at = now(), "
                    "attempts = attempts + 1, delivered_to = :d, last_error_code = NULL "
                    "WHERE id = :id"
                ),
                {"id": row.id, "d": sorted(served)},
            )
            counts["sent"] += 1
            return
        if not failed_any:  # only the rate limit stopped us: no attempt is spent
            await conn.execute(
                text(
                    "UPDATE admin.notifications SET delivered_to = :d WHERE id = :id"
                ),
                {"id": row.id, "d": sorted(served)},
            )
            return
        attempts = row.attempts + 1
        if attempts >= self._max_attempts:
            await conn.execute(
                text(
                    "UPDATE admin.notifications SET status = 'failed', attempts = :a, "
                    "delivered_to = :d, last_error_code = 'delivery_failed' WHERE id = :id"
                ),
                {"id": row.id, "a": attempts, "d": sorted(served)},
            )
            counts["failed"] += 1
        else:
            delay = min(BACKOFF_CAP, BACKOFF_BASE * 2 ** (attempts - 1))
            await conn.execute(
                text(
                    "UPDATE admin.notifications SET attempts = :a, delivered_to = :d, "
                    "next_attempt_at = now() + make_interval(secs => :delay), "
                    "last_error_code = 'delivery_failed' "
                    "WHERE id = :id"
                ),
                {
                    "id": row.id,
                    "a": attempts,
                    "d": sorted(served),
                    "delay": float(delay),
                },
            )
            counts["retried"] += 1

    async def _finish(self, conn, row_id, status, code, attempts) -> None:
        await conn.execute(
            text(
                "UPDATE admin.notifications SET status = :s, attempts = :a, "
                "last_error_code = :c WHERE id = :id"
            ),
            {"id": row_id, "s": status, "a": attempts + 1, "c": code},
        )

    async def _summarise(self, counts: Mapping[str, int]) -> None:
        """One audit row per batch with counts only; a failure here is logged
        and never undoes the status updates (the mails already went out)."""
        try:
            async with self._engine.begin() as conn:
                await audit.write(
                    conn,
                    "notifications.batch",
                    "notifications",
                    None,
                    None,
                    {
                        "sent": counts["sent"],
                        "retried": counts["retried"],
                        "failed": counts["failed"],
                        "mails": counts["mails"],
                    },
                    "success",
                    actor_kind="system",
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("notification summary not audited (%s)", type(exc).__name__)
