"""A small runner for the admin service's background loops.

One asyncio task per loop. Each loop is guarded by a lease: a row in
``admin.loop_leases`` (migration 0013) that the leader renews on every pass and
that expires on its own, so with several admin processes only one runs a given
loop; the others stand by and retry, and take over when a crashed leader's lease
runs out. The lease table is writable by the admin role only: unlike a session
advisory lock (one cluster-wide namespace every database login can use) no
outsider can hold it to stop the loops. A loop never crashes the service: an
exception is caught, logged by class name only, counted, and the loop backs off.
Intervals are jittered. Cancellation is clean: the lease is released before the
task ends.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import Callable, Dict, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.loops.status import LoopStatus, StatusBoard
from backend.admin.security.clock import Clock

log = logging.getLogger("backend.admin.loops")

MAX_BACKOFF_FACTOR = 8
MIN_LEASE_SECONDS = 120.0

# take the lease when it is free, expired or already ours (renewing it); no row
# comes back when someone else holds an unexpired one
_LEASE = text(
    "INSERT INTO admin.loop_leases AS l (name, holder, acquired_at, expires_at) "
    "VALUES (:n, :h, clock_timestamp(), clock_timestamp() + make_interval(secs => :ttl)) "
    "ON CONFLICT (name) DO UPDATE SET holder = excluded.holder, "
    "acquired_at = CASE WHEN l.holder = excluded.holder THEN l.acquired_at "
    "ELSE excluded.acquired_at END, expires_at = excluded.expires_at "
    "WHERE l.holder = excluded.holder OR l.expires_at < clock_timestamp() "
    "RETURNING 1"
)
_RELEASE = text(
    "UPDATE admin.loop_leases SET expires_at = clock_timestamp() "
    "WHERE name = :n AND holder = :h"
)
JITTER = 0.1


class Loop:
    """One background job. ``run_once`` returns a short outcome phrase made of
    fixed words and counts; it must not include payloads, addresses or secrets."""

    name: str = ""
    lock_number: int = 0
    interval: float = 60.0

    async def run_once(self) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class LoopRunner:
    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        loops: Sequence[Loop],
        board: Optional[StatusBoard] = None,
        *,
        standby_retry: float = 30.0,
        lease_seconds: Optional[float] = None,
        jitter: Callable[[], float] = lambda: random.uniform(-JITTER, JITTER),
    ) -> None:
        numbers = [loop.lock_number for loop in loops]
        if len(set(numbers)) != len(numbers) or any(n <= 0 for n in numbers):
            raise ValueError("every loop needs its own positive lock number")
        self._engine = engine
        self._clock = clock
        self._loops = list(loops)
        self.board = board if board is not None else StatusBoard()
        self._standby_retry = standby_retry
        self._lease_seconds = lease_seconds
        self._holder = uuid.uuid4().hex
        self._jitter = jitter
        self._tasks: list = []

    # ------------------------------------------------------------ status

    def status(self) -> Dict[str, LoopStatus]:
        """A read-only copy of every loop's state (for the Health page)."""
        return self.board.snapshot()

    # ----------------------------------------------------------- control

    async def start(self) -> None:
        if self._tasks:
            return
        for loop in self._loops:
            self.board.update(loop.name)
            self._tasks.append(
                asyncio.create_task(self._run(loop), name=f"admin-loop-{loop.name}")
            )
        self.board.running = True

    async def stop(self) -> None:
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.board.running = False

    # ------------------------------------------------------------- lease

    def _ttl(self, loop: Loop) -> float:
        """Long enough that a leader that is slow (not dead) keeps its lease: three
        intervals, never under two minutes, so a crash is noticed within that."""
        if self._lease_seconds is not None:
            return self._lease_seconds
        return max(MIN_LEASE_SECONDS, loop.interval * 3)

    async def _lease(self, loop: Loop) -> bool:
        """Take or renew the loop's lease; ``False`` when another holds it."""
        async with self._engine.begin() as conn:
            row = await conn.execute(
                _LEASE, {"n": loop.name, "h": self._holder, "ttl": self._ttl(loop)}
            )
            return row.first() is not None

    async def _release(self, loop: Loop) -> None:
        try:
            async with self._engine.begin() as conn:
                await conn.execute(_RELEASE, {"n": loop.name, "h": self._holder})
        except BaseException:  # noqa: BLE001 - include a second cancellation
            pass  # the lease simply expires

    # -------------------------------------------------------------- loop

    def _delay(self, loop: Loop, failures: int) -> float:
        factor = min(2**failures, MAX_BACKOFF_FACTOR) if failures else 1
        return max(0.01, loop.interval * factor * (1 + self._jitter()))

    async def _run(self, loop: Loop) -> None:
        failures = 0
        held = False
        try:
            while True:
                delay = loop.interval
                try:
                    held = await self._lease(loop)
                    if not held:
                        status = self.board.loops.get(loop.name)
                        self.board.update(
                            loop.name,
                            leader=False,
                            last_outcome="standby",
                            standby_since=(
                                status.standby_since
                                if status is not None and status.standby_since
                                else self._clock.now()
                            ),
                        )
                        delay = self._standby_retry
                    else:
                        outcome = await loop.run_once()
                        failures = 0
                        self.board.update(
                            loop.name,
                            leader=True,
                            standby_since=None,
                            last_run_at=self._clock.now(),
                            last_outcome=outcome,
                            last_ok=True,
                            consecutive_failures=0,
                            runs=self.board.loops[loop.name].runs + 1,
                        )
                        delay = self._delay(loop, 0)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # never crash the service
                    failures += 1
                    # the class name only: messages can carry addresses or SQL
                    log.warning(
                        "admin loop %s failed (%s), %d in a row",
                        loop.name, type(exc).__name__, failures,
                    )
                    self.board.update(
                        loop.name,
                        leader=held,
                        last_run_at=self._clock.now(),
                        last_outcome=f"failed: {type(exc).__name__}"[:80],
                        last_ok=False,
                        consecutive_failures=failures,
                        runs=self.board.loops[loop.name].runs + 1,
                    )
                    delay = self._delay(loop, failures)
                await asyncio.sleep(delay)
        finally:
            if held:
                await self._release(loop)
            self.board.update(loop.name, leader=False)
