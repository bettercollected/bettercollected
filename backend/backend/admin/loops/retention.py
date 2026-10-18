"""Retention: what the admin service removes on its own, and nothing else.

| table | removed |
| --- | --- |
| sessions, sign-in challenges | the existing cleanup (finished 7 days / expired 1 day ago) |
| rate-limit counters (``admin.attempts``, incl. used step-up tokens) | older than twice the longest window |
| ``tasks.run_events`` | older than 90 days |
| ``tasks.checkpoints`` | of runs finished more than 30 days ago |
| ``settings.service_state`` | rows older than 7 days of a service with no newer row |

Every statement is bounded (``LIMIT``), so one pass never holds a long lock; a
backlog drains over the next passes. The audit log and the settings entries,
history and manifest are never touched here (the role has no DELETE on them).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Awaitable, Callable, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.loops.base import Loop
from backend.admin.security.clock import Clock

log = logging.getLogger("backend.admin.loops")

RUN_EVENTS_DAYS = 90
CHECKPOINTS_DAYS = 30
SERVICE_STATE_DAYS = 7
BOUND = 1000  # rows per statement per pass


class StepsFailed(Exception):
    """One or more retention steps failed (the others still ran)."""


class RetentionLoop(Loop):
    name = "retention"
    lock_number = 2

    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        sessions_cleanup: Callable[[], Awaitable[object]],
        limiter_cleanup: Callable[[], Awaitable[object]],
        *,
        interval: float = 3600.0,
        bound: int = BOUND,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._sessions = sessions_cleanup
        self._limiter = limiter_cleanup
        self.interval = interval
        self._bound = bound

    async def _delete(self, sql: str, **params) -> int:
        async with self._engine.begin() as conn:
            result = await conn.execute(text(sql), {"n": self._bound, **params})
            return int(result.rowcount or 0)

    async def run_once(self) -> str:
        now = self._clock.now()
        done: Dict[str, int] = {}
        failed: List[str] = []

        async def step(name: str, call: Callable[[], Awaitable[object]]) -> None:
            try:
                result = await call()
            except Exception as exc:  # noqa: BLE001 - class only
                log.warning("retention step %s failed (%s)", name, type(exc).__name__)
                failed.append(name)
                return
            done[name] = sum(result.values()) if isinstance(result, dict) else int(result or 0)

        await step("sessions", self._sessions)
        await step("limiter", self._limiter)
        await step(
            "run_events",
            lambda: self._delete(
                "DELETE FROM tasks.run_events WHERE id IN ("
                "SELECT id FROM tasks.run_events WHERE at < :cut ORDER BY id LIMIT :n)",
                cut=now - timedelta(days=RUN_EVENTS_DAYS),
            ),
        )
        await step(
            "checkpoints",
            lambda: self._delete(
                "DELETE FROM tasks.checkpoints WHERE id IN ("
                "SELECT c.id FROM tasks.checkpoints c "
                "JOIN tasks.runs r ON r.id = c.run_id "
                "WHERE r.finished_at < :cut ORDER BY c.id LIMIT :n)",
                cut=now - timedelta(days=CHECKPOINTS_DAYS),
            ),
        )
        await step(
            "service_state",
            lambda: self._delete(
                "DELETE FROM settings.service_state WHERE ctid IN ("
                "SELECT s.ctid FROM settings.service_state s "
                "WHERE s.reported_at < :cut AND NOT EXISTS ("
                "SELECT 1 FROM settings.service_state f "
                "WHERE f.service = s.service AND f.reported_at >= :cut) "
                "ORDER BY s.reported_at LIMIT :n)",
                cut=now - timedelta(days=SERVICE_STATE_DAYS),
            ),
        )
        summary = ", ".join(f"{k} {v}" for k, v in done.items())
        if failed:
            raise StepsFailed(",".join(failed))
        return f"removed: {summary}"
