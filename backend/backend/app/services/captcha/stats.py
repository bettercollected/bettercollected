"""Counts of the automatic spam check, by day (``captcha_daily_counts``): what
happened (issued, verified, refused for which reason, rate limited), for which
form and purpose. Counts only: no address, no client, no tag, no challenge, no
person, and nothing about a single request.

Written off the request path. ``record`` is a counter in this process's memory
(a dictionary, bounded) and returns at once; the counts are added to the table
in one transaction every 60 seconds, or when 500 different keys are waiting,
whichever comes first, and when a page asks for them (so the answer includes
what this process has not written yet). A flood of refused requests therefore
costs a dictionary entry, never a database write: its keys are the form's and
the day's, not the client's. Counts a crash loses, or a database that cannot be
reached drops beyond ``MAX_KEYS``, are lost: these are statistics, not a ledger.

Only reached while ``CAPTCHA_ENABLED`` is on: every caller is behind the switch,
so off, nothing is counted and nothing is written.
"""

import asyncio
import datetime as dt
import time
from typing import Callable, Dict, Optional, Set, Tuple

from loguru import logger

from backend.app.repositories.postgres.analytics import (
    CountKey,
    PostgresCaptchaCountRepository,
)

FLUSH_SECONDS = 60
FLUSH_KEYS = 500
# waiting keys never grow past this (a database that stays unreachable): new keys are dropped
MAX_KEYS = 5000
SWEEP_SECONDS = 24 * 3600
# the window the pages read
WINDOW_DAYS = 30

# a refused proof, whatever the reason: not a verified one
REFUSED = ("missing", "invalid", "expired", "replayed")
PURPOSES = ("submit", "mail")


def day_of(now: float) -> str:
    return dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")


class CaptchaStats:
    def __init__(
        self,
        repo: PostgresCaptchaCountRepository,
        clock: Callable[[], float] = time.time,
        retention_days: Optional[Callable[[], int]] = None,
    ):
        self._repo = repo
        self._clock = clock
        self._retention_days = retention_days or _retention_days
        self._waiting: Dict[CountKey, int] = {}
        self._last_flush = clock()
        self._last_sweep: Optional[float] = None
        self._lock: Optional[asyncio.Lock] = None
        self._tasks: Set["asyncio.Task[None]"] = set()
        # a flush started by ``record`` that has not finished: no second one is started
        self._scheduled = False
        # after a failed write nothing starts a flush before this time (a slow or
        # down database must not see one write attempt per request)
        self._retry_at = 0.0

    # -- writing

    def record(
        self, outcome: str, purpose: str, workspace_id="", form_id=""
    ) -> None:
        """Count one outcome in memory. Never raises, never waits. The refusal
        codes (``captcha_missing`` ...) are counted as ``missing`` ..."""
        try:
            outcome = outcome.removeprefix("captcha_")
            key = (
                day_of(self._clock()),
                str(workspace_id or ""),
                str(form_id or ""),
                purpose,
                outcome,
            )
            if key not in self._waiting and len(self._waiting) >= MAX_KEYS:
                return
            self._waiting[key] = self._waiting.get(key, 0) + 1
            self._flush_if_due()
        except Exception:  # noqa: BLE001 - statistics never fail a request
            return

    def _flush_if_due(self) -> None:
        now = self._clock()
        if self._scheduled or now < self._retry_at:
            return
        due = len(self._waiting) >= FLUSH_KEYS or now - self._last_flush >= FLUSH_SECONDS
        if not due:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        # one at a time: claimed now, so that a burst of requests starts one flush
        # (and, while it runs or after it failed, none)
        self._scheduled = True
        self._last_flush = now
        task = loop.create_task(self.flush())
        self._tasks.add(task)
        task.add_done_callback(self._flush_done)

    def _flush_done(self, task: "asyncio.Task[None]") -> None:
        self._scheduled = False
        self._tasks.discard(task)

    async def flush(self) -> None:
        """Add the waiting counts to the table. A failure keeps them for the
        next flush (bounded) and is logged by its type only."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            counts, self._waiting = self._waiting, {}
            self._last_flush = self._clock()
            if counts:
                try:
                    await self._repo.add_counts(counts)
                except Exception as error:  # noqa: BLE001 - never raised to a request
                    logger.warning(
                        "captcha counts not written ({} keys kept for later, {})",
                        len(counts),
                        type(error).__name__,
                    )
                    self._keep(counts)
                    # back off: no flush is started by a request for a while
                    self._retry_at = self._clock() + FLUSH_SECONDS
                    return
            await self._sweep()

    def _keep(self, counts: Dict[CountKey, int]) -> None:
        for key, amount in counts.items():
            if key not in self._waiting and len(self._waiting) >= MAX_KEYS:
                continue
            self._waiting[key] = self._waiting.get(key, 0) + amount

    async def _sweep(self) -> None:
        """Retention, as for the flow events: counts older than
        ``API_FLOW_EVENTS_RETENTION_DAYS`` go, at most once a day per process
        (0 keeps them)."""
        days = self._retention_days()
        now = self._clock()
        if days <= 0 or (
            self._last_sweep is not None and now - self._last_sweep < SWEEP_SECONDS
        ):
            return
        self._last_sweep = now
        try:
            await self._repo.delete_before(day_of(now - days * 86400))
        except Exception as error:  # noqa: BLE001
            logger.warning("captcha counts not swept ({})", type(error).__name__)

    # -- reading

    async def summary(
        self,
        *,
        workspace_id: Optional[str] = None,
        form_id: Optional[str] = None,
        days: int = WINDOW_DAYS,
    ) -> dict:
        """The last ``days`` days of one workspace or form, by purpose:
        ``{"days", "submit": {"passed", "blocked"}, "mail": {...}}``. ``passed``
        counts proofs that verified, ``blocked`` those refused (missing, invalid,
        expired or already used); challenges handed out and rate limits are in
        the table but not in this answer. What this process has not written yet
        is written first."""
        await self.flush()
        since = day_of(self._clock() - (days - 1) * 86400)
        totals: Dict[Tuple[str, str], int] = await self._repo.totals(
            since_day=since, workspace_id=workspace_id, form_id=form_id
        )
        answer: dict = {"days": days}
        for purpose in PURPOSES:
            answer[purpose] = {
                "passed": totals.get((purpose, "verified"), 0),
                "blocked": sum(totals.get((purpose, o), 0) for o in REFUSED),
            }
        return answer


def _retention_days() -> int:
    from backend.config import settings

    return int(settings.api_settings.FLOW_EVENTS_RETENTION_DAYS)
