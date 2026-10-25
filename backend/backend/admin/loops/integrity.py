"""The integrity monitor.

Every pass it runs the settings store's ``verify()`` (signatures, manifest,
audit cross-check), verifies the next bounded slice of the audit chain from a
stored checkpoint (``audit_chain_broken`` / ``audit_checkpoint_bad``), probes the
two row locks the admin writes depend on (``lock_blocked``: a holder that keeps
one for longer than the 5 s lock timeout), reads the keys that running
services reported as rejected (only names the registry knows) and asks
``admin.credential_purges_overdue()`` whether a deleted account's stored
provider credentials are still not purged a day later (``CREDENTIAL_PURGE``,
``overdue``; a count only). Any problem is shown on the shell banner (through the shared status
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
from sqlalchemy.exc import DBAPIError
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
        audit_step: Optional[Callable[[], Awaitable[object]]] = None,
        known_keys: Optional[Callable[[], frozenset]] = None,
        probe_locks: bool = True,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._verify = verify
        self._board = board
        self._audit_step = audit_step
        self._known_keys = known_keys
        self._probe_locks = probe_locks
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
        if self._audit_step is not None:
            step = await asyncio.wait_for(self._audit_step(), VERIFY_TIMEOUT)
            for _, why in getattr(step, "breaks", ()):
                found.add(
                    ("*", "audit_chain_broken" if why.endswith("_hash_mismatch") else "audit_checkpoint_bad")
                )
        if self._probe_locks and await self._lock_blocked():
            found.add(("*", "lock_blocked"))
        known = self._known_keys() if self._known_keys is not None else None
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
                # a reported name counts only when the registry knows it: a service
                # cannot raise alarms (and mail every admin) about names it invents
                if _KEY.match(str(key)) and (known is None or key in known):
                    found.add((key, "rejected_by_reader"))
        if await self._store_behind_services(since):
            found.add(("*", "store_behind_services"))
        if await self._credential_purges_overdue():
            found.add(("CREDENTIAL_PURGE", "overdue"))
        return tuple(sorted(found))[:MAX_PROBLEMS]

    async def _credential_purges_overdue(self) -> bool:
        """A deleted account's stored provider credentials not purged a day
        after the purge was queued (or the purge, or the deletion job, failed):
        ``admin.credential_purges_overdue()`` (postgres/ensure-admin-roles.sh),
        a count only. A stack without it (or without the job queue) has none."""
        try:
            async with self._engine.connect() as conn:
                present = (
                    await conn.execute(
                        text(
                            "SELECT to_regprocedure('admin.credential_purges_overdue()') "
                            "IS NOT NULL"
                        )
                    )
                ).scalar()
                if not present:
                    return False
                overdue = (
                    await conn.execute(text("SELECT admin.credential_purges_overdue()"))
                ).scalar()
        except DBAPIError as exc:
            log.warning(
                "integrity: credential purge check unavailable (%s)",
                type(exc.orig).__name__ if exc.orig is not None else "error",
            )
            return False
        return bool(overdue)

    async def _lock_blocked(self) -> bool:
        """Whether the audit chain's or the settings writer's lock cannot be taken
        (twice, 5 s each): somebody holds it for far longer than any write needs.
        Only the admin roles can take these locks, so this is the portal, the CLI or
        the runner stuck, never an outsider; the audit and settings writes fail
        (clearly, after 5 s) while it lasts."""
        for name in ("audit_chain", "settings_writer"):
            for attempt in range(2):
                try:
                    async with self._engine.begin() as conn:
                        await conn.execute(text("SELECT admin.take_lock(:n)"), {"n": name})
                    break
                except DBAPIError as exc:
                    sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
                    if sqlstate != "55P03":
                        raise
                    if attempt == 1:
                        return True
        return False

    async def _store_behind_services(self, since: datetime) -> bool:
        """The rollback floor that does not live in a container: running services
        report the highest revision they accepted, and the store never legitimately
        shows a lower manifest revision than that. A restored backup or a
        replaced database does, even when its own audit trail was restored too."""
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT (SELECT revision FROM settings.manifest WHERE id = 1) AS stored, "
                        "(SELECT coalesce(max(revision_applied), 0) FROM settings.service_state "
                        " WHERE reported_at >= :since) AS applied"
                    ),
                    {"since": since},
                )
            ).first()
        if row is None or row.stored is None:
            return False
        return int(row.applied) > int(row.stored)

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
