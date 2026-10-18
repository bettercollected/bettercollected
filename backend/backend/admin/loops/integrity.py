"""The integrity monitor.

Every pass it runs the settings store's ``verify()`` (signatures, manifest,
audit cross-check) and reads the keys that running services reported as
rejected. Any problem is shown on the shell banner (through the shared status
board) and mailed once per incident: the same set of problems is not mailed
again within 24 hours (kept in memory, and, after a restart, in the outbox row's
``dedupe_key``). When the problems are gone the status returns to ok, and a
later recurrence is a new incident. Notices name settings and fixed reason
codes only, never values.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Awaitable, Callable, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.loops.base import Loop
from backend.admin.loops.status import IntegrityStatus, StatusBoard
from backend.admin.repositories import settings as repo
from backend.admin.security.clock import Clock
from backend.admin.services import audit

log = logging.getLogger("backend.admin.loops")

REMAIL_AFTER = timedelta(hours=24)
VERIFY_TIMEOUT = 60.0
REPORT_FRESH = timedelta(hours=1)  # only live instances' rejected keys count
MAX_PROBLEMS = 200  # considered per pass
SHOWN = 50  # kept on the status
MAILED = 10  # named in the notice

_KEY = re.compile(r"^(\*|[A-Z][A-Z0-9_]{0,63})$")
_REASON = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

Problems = Tuple[Tuple[str, str], ...]


def fingerprint(problems: Problems) -> str:
    body = "\n".join(f"{k}:{r}" for k, r in problems)
    return hashlib.sha256(body.encode()).hexdigest()[:32]


class IntegrityMonitor(Loop):
    name = "integrity"
    lock_number = 3

    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        verify: Callable[[], Awaitable[Sequence[object]]],
        board: StatusBoard,
        *,
        interval: float = 600.0,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._verify = verify
        self._board = board
        self.interval = interval
        # fingerprint and moment of the last notice from this process
        self._known: Optional[Tuple[str, datetime]] = None
        self._first = True

    async def _collect(self) -> Problems:
        found = set()
        for problem in await asyncio.wait_for(self._verify(), VERIFY_TIMEOUT):
            key = getattr(problem, "key", "")
            reason = getattr(problem, "reason", "")
            found.add(
                (
                    key if _KEY.match(str(key)) else "*",
                    reason if _REASON.match(str(reason)) else "other",
                )
            )
        since = self._clock.now() - REPORT_FRESH
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT rejected_keys FROM settings.service_state "
                        "WHERE reported_at >= :since AND cardinality(rejected_keys) > 0 "
                        "LIMIT 200"
                    ),
                    {"since": since},
                )
            ).all()
        for row in rows:
            for key in row.rejected_keys or []:
                if _KEY.match(str(key)):
                    found.add((key, "rejected_by_reader"))
        return tuple(sorted(found))[:MAX_PROBLEMS]

    async def run_once(self) -> str:
        now = self._clock.now()
        problems = await self._collect()
        if not problems:
            self._known = None
            self._first = False
            self._board.integrity = IntegrityStatus(True, (), now)
            return "ok"
        self._board.integrity = IntegrityStatus(False, problems[:SHOWN], now)
        fp = fingerprint(problems)
        notified = await self._notify_once(fp, problems, now)
        self._first = False
        return f"{len(problems)} problem(s), {'notified' if notified else 'already notified'}"

    async def _notify_once(self, fp: str, problems: Problems, now: datetime) -> bool:
        if self._known is not None:
            known_fp, at = self._known
            if known_fp == fp and now - at < REMAIL_AFTER:
                return False
        key = f"integrity:{fp}"
        async with self._engine.begin() as conn:
            if self._first and self._known is None:  # after a restart: ask the outbox
                seen = (
                    await conn.execute(
                        text(
                            "SELECT 1 FROM admin.notifications "
                            "WHERE dedupe_key = :k AND created_at >= :since LIMIT 1"
                        ),
                        {"k": key, "since": now - REMAIL_AFTER},
                    )
                ).first()
                if seen:
                    self._known = (fp, now)
                    return False
            written = await audit.write(
                conn,
                "integrity.problem_found",
                "settings_store",
                None,
                None,
                {"problems": len(problems)},
                "failure",
                actor_kind="system",
            )
            await repo.enqueue_notification(
                conn,
                "settings.integrity",
                {
                    "count": len(problems),
                    "problems": [{"key": k, "reason": r} for k, r in problems[:MAILED]],
                },
                written.seq,
                dedupe_key=key,
            )
        self._known = (fp, now)
        return True
