"""Attempt limits for sign-in, backed by one small counter table.

``AttemptStore`` is the whole storage contract: counters per ``(key,
window_start)`` with an atomic increment. ``MemoryAttemptStore`` serves tests;
``SqlAttemptStore`` is the PostgreSQL implementation (``INSERT ... ON
CONFLICT DO UPDATE ... RETURNING count``) over the table shaped as
``admin.attempts(key, window_start, count)``; creating that table is the
migration's job, ``build_attempts_table`` only describes it.

``Limiter`` applies the sign-in rules on top. Windows are fixed (aligned to
the epoch), so a burst straddling a boundary can briefly reach twice a limit;
the lockouts and the global breaker bound what that is worth to an attacker.
Keys never contain a raw email or address: they are HMAC digests under a
pepper, so the table reveals nothing by itself.

The lockout deadline is stored in the ``window_start`` column of a ``lock:``
row, which keeps the whole state in the one table.
"""

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Protocol, Tuple, runtime_checkable

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.security.clock import Clock
from backend.admin.security.keycheck import require_key

# ---------------------------------------------------------------- storage


@runtime_checkable
class AttemptStore(Protocol):
    async def increment(self, key: str, window_start: datetime) -> int:
        """Atomically add one to the counter and return its new value."""
        ...

    async def count(self, key: str, window_start: datetime) -> int: ...

    async def sum_since(self, key: str, since: datetime) -> int:
        """Total of the counters of ``key`` whose ``window_start`` is at or
        after ``since`` (for rolling windows made of small buckets)."""
        ...

    async def latest_window(self, key: str) -> Optional[datetime]:
        """The newest ``window_start`` stored under ``key``."""
        ...

    async def reset(self, key: str) -> None:
        """Delete every counter of ``key``."""
        ...

    async def cleanup(self, before: datetime) -> int:
        """Delete counters whose ``window_start`` is older than ``before``;
        returns how many."""
        ...


class MemoryAttemptStore:
    """In-process store for tests (single event loop, so increments are atomic)."""

    def __init__(self) -> None:
        self.rows: Dict[Tuple[str, datetime], int] = {}

    async def increment(self, key: str, window_start: datetime) -> int:
        slot = (key, window_start)
        self.rows[slot] = self.rows.get(slot, 0) + 1
        return self.rows[slot]

    async def count(self, key: str, window_start: datetime) -> int:
        return self.rows.get((key, window_start), 0)

    async def sum_since(self, key: str, since: datetime) -> int:
        return sum(
            c for (k, start), c in self.rows.items() if k == key and start >= since
        )

    async def latest_window(self, key: str) -> Optional[datetime]:
        starts = [start for (k, start) in self.rows if k == key]
        return max(starts) if starts else None

    async def reset(self, key: str) -> None:
        for slot in [s for s in self.rows if s[0] == key]:
            del self.rows[slot]

    async def cleanup(self, before: datetime) -> int:
        stale = [s for s in self.rows if s[1] < before]
        for slot in stale:
            del self.rows[slot]
        return len(stale)


def build_attempts_table(metadata: MetaData, schema: Optional[str] = "admin") -> Table:
    """The shape of ``admin.attempts``."""
    return Table(
        "attempts",
        metadata,
        Column("key", Text, primary_key=True),
        Column("window_start", DateTime(timezone=True), primary_key=True),
        Column("count", Integer, nullable=False, server_default="0"),
        schema=schema,
    )


class SqlAttemptStore:
    """PostgreSQL store over a table built by ``build_attempts_table``."""

    def __init__(self, engine: AsyncEngine, table: Table) -> None:
        self._engine = engine
        self._table = table

    async def increment(self, key: str, window_start: datetime) -> int:
        t = self._table
        statement = pg_insert(t).values(key=key, window_start=window_start, count=1)
        statement = statement.on_conflict_do_update(
            index_elements=[t.c.key, t.c.window_start],
            set_={"count": t.c.count + 1},
        ).returning(t.c.count)
        async with self._engine.begin() as conn:
            return int((await conn.execute(statement)).scalar_one())

    async def count(self, key: str, window_start: datetime) -> int:
        t = self._table
        query = select(t.c.count).where(
            t.c.key == key, t.c.window_start == window_start
        )
        async with self._engine.connect() as conn:
            return int((await conn.execute(query)).scalar() or 0)

    async def sum_since(self, key: str, since: datetime) -> int:
        t = self._table
        query = select(func.coalesce(func.sum(t.c.count), 0)).where(
            t.c.key == key, t.c.window_start >= since
        )
        async with self._engine.connect() as conn:
            return int((await conn.execute(query)).scalar() or 0)

    async def latest_window(self, key: str) -> Optional[datetime]:
        t = self._table
        query = select(func.max(t.c.window_start)).where(t.c.key == key)
        async with self._engine.connect() as conn:
            return (await conn.execute(query)).scalar()

    async def reset(self, key: str) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(delete(self._table).where(self._table.c.key == key))

    async def cleanup(self, before: datetime) -> int:
        statement = delete(self._table).where(self._table.c.window_start < before)
        async with self._engine.begin() as conn:
            return int((await conn.execute(statement)).rowcount or 0)


# ------------------------------------------------------------------ rules


@dataclass(frozen=True)
class Rule:
    """At most ``limit`` events per ``window_seconds`` (fixed window)."""

    name: str
    limit: int
    window_seconds: int


CODE_REQUEST_PER_EMAIL = Rule("code_email", 3, 600)
CODE_REQUEST_PER_IP = Rule("code_ip", 10, 600)
CHALLENGE_ATTEMPTS = Rule("challenge", 5, 600)
FACTOR_FAILURES = Rule("factor_fail", 5, 300)
GLOBAL_FAILURES = Rule("global_fail", 50, 600)
# slow guessing: failures in any rolling 24 h, counted in 15-minute buckets
LONG_FAILURE_LIMIT = 15
LONG_WINDOW_SECONDS = 24 * 60 * 60
LONG_BUCKET_SECONDS = 15 * 60
# one address contributes at most this many failures to the global breaker
# per breaker window, so one source cannot trip it alone
GLOBAL_PER_IP_CAP = 5
LOCKOUT_SECONDS = (15 * 60, 60 * 60, 4 * 60 * 60)
STRIKE_WINDOW_SECONDS = 24 * 60 * 60
GLOBAL_PAUSE_SECONDS = 10 * 60
_GLOBAL_SUBJECT = "all"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    count: int
    limit: int
    retry_after: int  # seconds until the window ends; 0 when allowed


@dataclass(frozen=True)
class LockStatus:
    locked: bool
    until: Optional[datetime]
    retry_after: int


@dataclass(frozen=True)
class FailureOutcome:
    locked: bool
    newly_locked: bool  # the caller should notify administrators once
    level: int  # 0 when not locked, 1..3 escalation step
    until: Optional[datetime]
    retry_after: int


@dataclass(frozen=True)
class BreakerOutcome:
    paused: bool
    newly_tripped: bool  # the caller should notify administrators once
    retry_after: int


# ------------------------------------------------------------------- keys


def normalise_email(email: str) -> str:
    return str(email).strip().lower()


def ip_bucket(client: Optional[str]) -> str:
    """The address a client is limited under: IPv4 as is, IPv6 by its /64,
    ``unknown`` when it can't be parsed.

    Same behaviour as ``backend.app.utils.client_ip.rate_limit_key``. That
    module can't be imported here: its package pulls in the whole public
    application, which the admin service must never load. A test keeps the
    two in step."""
    try:
        address = ipaddress.ip_address((client or "").strip().split("%", 1)[0])
    except ValueError:
        return "unknown"
    mapped = getattr(address, "ipv4_mapped", None)
    address = mapped or address
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def hashed_key(pepper: bytes, kind: str, identifier: str) -> str:
    digest = hmac.new(
        pepper, f"{kind}\x00{identifier}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{kind}:{digest}"


# ---------------------------------------------------------------- limiter


class Limiter:
    def __init__(self, store: AttemptStore, clock: Clock, pepper: bytes) -> None:
        self._store = store
        self._clock = clock
        self._pepper = require_key(pepper, "rate limit key")

    # keys
    def email_key(self, email: str) -> str:
        return hashed_key(self._pepper, "email", normalise_email(email))

    def ip_key(self, client: Optional[str]) -> str:
        return hashed_key(self._pepper, "ip", ip_bucket(client))

    # helpers
    def _window(self, rule: Rule) -> Tuple[datetime, int]:
        """``(window_start, seconds left in the window)``."""
        now = self._clock.time()
        start = int(now // rule.window_seconds) * rule.window_seconds
        left = max(1, int(start + rule.window_seconds - now))
        return datetime.fromtimestamp(start, timezone.utc), left

    def _until(self, seconds: int) -> datetime:
        return datetime.fromtimestamp(self._clock.time() + seconds, timezone.utc)

    def _retry(self, until: datetime) -> int:
        return max(1, int(until.timestamp() - self._clock.time()))

    async def hit(self, rule: Rule, subject: str) -> Decision:
        """Count one event of ``rule`` for ``subject`` (a key from
        ``email_key`` / ``ip_key`` / a challenge id digest)."""
        start, left = self._window(rule)
        count = await self._store.increment(f"{rule.name}:{subject}", start)
        allowed = count <= rule.limit
        return Decision(allowed, count, rule.limit, 0 if allowed else left)

    # sign-in code requests
    async def request_code(self, email: str, client: Optional[str]) -> Decision:
        """Both code-request limits; the answer is the stricter. Both are
        counted, so a refusal by one doesn't hide the other's tally."""
        by_email = await self.hit(CODE_REQUEST_PER_EMAIL, self.email_key(email))
        by_ip = await self.hit(CODE_REQUEST_PER_IP, self.ip_key(client))
        if not by_email.allowed or not by_ip.allowed:
            retry = max(by_email.retry_after, by_ip.retry_after)
            first = by_email if not by_email.allowed else by_ip
            return Decision(False, first.count, first.limit, retry)
        return by_email

    # code verification attempts
    async def challenge_attempt(
        self, challenge_id: str, expires_at: datetime
    ) -> Decision:
        """Count one guess at a sign-in challenge: five are allowed in its
        life. The counter lives in one bucket keyed by the challenge's expiry
        (so ``cleanup`` removes it once the challenge is long gone)."""
        key = hashed_key(self._pepper, "challenge", challenge_id)
        count = await self._store.increment(
            f"{CHALLENGE_ATTEMPTS.name}:{key}", expires_at
        )
        allowed = count <= CHALLENGE_ATTEMPTS.limit
        retry = 0 if allowed else self._retry(expires_at)
        return Decision(allowed, count, CHALLENGE_ATTEMPTS.limit, retry)

    # second factor failures and lockout
    def _subject_keys(self, subject: str) -> Tuple[str, str, str]:
        base = hashed_key(self._pepper, "factor", normalise_email(subject))
        return base + ":fail", base + ":strikes", base + ":lock"

    async def lock_status(self, subject: str) -> LockStatus:
        """Whether ``subject`` (an admin email) is locked out right now."""
        _, _, lock_key = self._subject_keys(subject)
        until = await self._store.latest_window(lock_key)
        if until is not None and until.timestamp() > self._clock.time():
            return LockStatus(True, until, self._retry(until))
        return LockStatus(False, None, 0)

    async def _trip(self, subject: str) -> FailureOutcome:
        """Lock ``subject``: 15 min, then 1 h, then 4 h for each further
        lockout within a day."""
        _, strike_key, lock_key = self._subject_keys(subject)
        strike_start, _ = self._window(Rule("strikes", 1, STRIKE_WINDOW_SECONDS))
        strikes = await self._store.increment(strike_key, strike_start)
        level = min(strikes, len(LOCKOUT_SECONDS))
        until = self._until(LOCKOUT_SECONDS[level - 1])
        await self._store.increment(lock_key, until)
        return FailureOutcome(True, True, level, until, self._retry(until))

    async def record_failure(self, subject: str) -> FailureOutcome:
        """Count a wrong TOTP / recovery code. Two rules lock the subject
        (and share the escalation): five failures in five minutes, and
        fifteen in any rolling 24 hours (which catches slow guessing that
        stays under the short rule). A failure while already locked is not
        counted and reports the lock."""
        status = await self.lock_status(subject)
        if status.locked:
            return FailureOutcome(True, False, 0, status.until, status.retry_after)
        fail_key, _, _ = self._subject_keys(subject)
        long_key = fail_key + ":long"
        start, _ = self._window(FACTOR_FAILURES)
        short = await self._store.increment(fail_key, start)
        bucket = int(self._clock.time() // LONG_BUCKET_SECONDS) * LONG_BUCKET_SECONDS
        await self._store.increment(
            long_key, datetime.fromtimestamp(bucket, timezone.utc)
        )
        since = datetime.fromtimestamp(
            self._clock.time() - LONG_WINDOW_SECONDS, timezone.utc
        )
        long_total = await self._store.sum_since(long_key, since)
        if short == FACTOR_FAILURES.limit or long_total >= LONG_FAILURE_LIMIT:
            if long_total >= LONG_FAILURE_LIMIT:
                await self._store.reset(long_key)  # start over after the lockout
            return await self._trip(subject)
        if short > FACTOR_FAILURES.limit:  # concurrent overshoot
            again = await self.lock_status(subject)
            return FailureOutcome(
                again.locked, False, 0, again.until, again.retry_after
            )
        return FailureOutcome(False, False, 0, None, 0)

    async def record_success(self, subject: str) -> None:
        """A correct code: the five-minute failure counter and the escalation
        reset. It does not clear an active lockout (callers check
        ``lock_status`` before verifying, so a locked subject never gets
        here) and it does not clear the rolling 24 h tally, so slow guessing
        cannot be wiped by a legitimate sign-in."""
        fail_key, strike_key, _ = self._subject_keys(subject)
        await self._store.reset(fail_key)
        await self._store.reset(strike_key)

    async def unlock(self, subject: str) -> None:
        """Operator override: clear failures, escalation and any lockout."""
        for key in self._subject_keys(subject):
            await self._store.reset(key)
        await self._store.reset(self._subject_keys(subject)[0] + ":long")

    # global breaker
    def _global_keys(self) -> Tuple[str, str]:
        base = hashed_key(self._pepper, "global", _GLOBAL_SUBJECT)
        return base + ":fail", base + ":pause"

    async def sign_in_pause(self) -> BreakerOutcome:
        """Whether sign-in is paused by the global breaker."""
        _, pause_key = self._global_keys()
        until = await self._store.latest_window(pause_key)
        if until is not None and until.timestamp() > self._clock.time():
            return BreakerOutcome(True, False, self._retry(until))
        return BreakerOutcome(False, False, 0)

    async def record_global_failure(
        self, client: Optional[str], identified_admin: bool
    ) -> BreakerOutcome:
        """Count a failed sign-in step toward the global breaker; the 50th
        within ten minutes pauses all sign-in for ten minutes.

        Only failures that cannot be produced by anyone on the internet count:
        pass ``identified_admin=True`` only for a failure after the email-code
        step of a configured admin (wrong challenge or factor code). Failures
        for unknown or non-admin emails are not counted (False), and one
        address (IPv6 by /64) contributes at most ``GLOBAL_PER_IP_CAP``
        failures per window, so a single source cannot trip the breaker. The
        pause is not extended by later failures and lifts by itself after
        ``GLOBAL_PAUSE_SECONDS``; ``resume_sign_in`` lifts it earlier."""
        if not identified_admin:
            return await self.sign_in_pause()
        fail_key, pause_key = self._global_keys()
        start, _ = self._window(GLOBAL_FAILURES)
        ip_count = await self._store.increment(self.ip_key(client) + ":gfail", start)
        if ip_count > GLOBAL_PER_IP_CAP:
            return await self.sign_in_pause()
        count = await self._store.increment(fail_key, start)
        if count < GLOBAL_FAILURES.limit:
            return BreakerOutcome(False, False, 0)
        if count == GLOBAL_FAILURES.limit:
            until = self._until(GLOBAL_PAUSE_SECONDS)
            await self._store.increment(pause_key, until)
            return BreakerOutcome(True, True, self._retry(until))
        return await self.sign_in_pause()

    async def resume_sign_in(self) -> None:
        """Operator override of the global breaker (see ``operator_resume``)."""
        for key in self._global_keys():
            await self._store.reset(key)

    async def cleanup(self, keep_seconds: int = 2 * STRIKE_WINDOW_SECONDS) -> int:
        """Drop counters older than ``keep_seconds``."""
        return await self._store.cleanup(self._until(-keep_seconds))


# ------------------------------------------------------------ operator hooks
#
# Entry points for the host CLI (``unlock`` and ``resume-sign-in``). They take
# the same store, clock and pepper as the service, so they reach the same
# rows, and need no HTTP.


async def operator_unlock(
    store: AttemptStore, clock: Clock, pepper: bytes, email: str
) -> None:
    """Clear failures, escalation and lockout of one admin email."""
    await Limiter(store, clock, pepper).unlock(email)


async def operator_resume(store: AttemptStore, clock: Clock, pepper: bytes) -> None:
    """Lift the global sign-in pause now (it also lifts itself)."""
    await Limiter(store, clock, pepper).resume_sign_in()
