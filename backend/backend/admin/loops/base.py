"""A small runner for the admin service's background loops.

One asyncio task per loop. Each loop is guarded by a Postgres session advisory
lock held on a dedicated connection, so with several admin processes only one
runs a given loop; the others stand by and retry. A loop never crashes the
service: an exception is caught, logged by class name only, counted, and the
loop backs off. Intervals are jittered. Cancellation is clean: the lock is
released (or its connection thrown away) before the task ends.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Callable, Dict, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.admin.loops.status import LoopStatus, StatusBoard
from backend.admin.security.clock import Clock

log = logging.getLogger("backend.admin.loops")

# first key of the two-int advisory lock form; the second is the loop's own number
LOCK_CLASS = 0x42434144
MAX_BACKOFF_FACTOR = 8
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

    # -------------------------------------------------------------- lock

    async def _acquire(self, loop: Loop) -> Optional[AsyncConnection]:
        conn = await self._engine.connect()
        try:
            got = (
                await conn.execute(
                    text("SELECT pg_try_advisory_lock(:c, :n)"),
                    {"c": LOCK_CLASS, "n": loop.lock_number},
                )
            ).scalar_one()
            await conn.commit()  # a session lock outlives the transaction
        except BaseException:
            await self._discard(conn)
            raise
        if got:
            return conn
        await conn.close()
        return None

    async def _alive(self, conn: AsyncConnection) -> bool:
        try:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
            return True
        except Exception:  # noqa: BLE001
            return False

    async def _discard(self, conn: AsyncConnection) -> None:
        try:
            await conn.invalidate()  # closes the session, which frees its locks
        except Exception:  # noqa: BLE001
            pass
        try:
            await conn.close()
        except Exception:  # noqa: BLE001
            pass

    async def _release(self, loop: Loop, conn: Optional[AsyncConnection]) -> None:
        if conn is None:
            return
        try:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:c, :n)"),
                {"c": LOCK_CLASS, "n": loop.lock_number},
            )
            await conn.commit()
            await conn.close()
        except BaseException:  # noqa: BLE001 - include a second cancellation
            await self._discard(conn)

    # -------------------------------------------------------------- loop

    def _delay(self, loop: Loop, failures: int) -> float:
        factor = min(2**failures, MAX_BACKOFF_FACTOR) if failures else 1
        return max(0.01, loop.interval * factor * (1 + self._jitter()))

    async def _run(self, loop: Loop) -> None:
        conn: Optional[AsyncConnection] = None
        failures = 0
        try:
            while True:
                delay = loop.interval
                try:
                    if conn is not None and not await self._alive(conn):
                        await self._discard(conn)
                        conn = None
                    if conn is None:
                        conn = await self._acquire(loop)
                    if conn is None:
                        self.board.update(
                            loop.name, leader=False, last_outcome="standby"
                        )
                        delay = self._standby_retry
                    else:
                        outcome = await loop.run_once()
                        failures = 0
                        self.board.update(
                            loop.name,
                            leader=True,
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
                        leader=conn is not None,
                        last_run_at=self._clock.now(),
                        last_outcome=f"failed: {type(exc).__name__}"[:80],
                        last_ok=False,
                        consecutive_failures=failures,
                        runs=self.board.loops[loop.name].runs + 1,
                    )
                    delay = self._delay(loop, failures)
                await asyncio.sleep(delay)
        finally:
            await self._release(loop, conn)
            self.board.update(loop.name, leader=False)
