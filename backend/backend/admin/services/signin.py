"""Email-code sign-in for the admin service (its own codes, not the public
platform's).

Properties the callers and tests rely on:

* ``request_code`` answers the same for every address. A challenge row exists
  only for a listed admin; everyone else gets a cookie that looks identical and
  leads nowhere. The database work and the HMAC work are of the same shape, and
  the mail goes out after the response, so timing does not tell them apart.
* A code is 8 digits, stored as ``HMAC-SHA256(pepper, challenge_id || code)``,
  valid 10 minutes, single use, five attempts per challenge; a new request kills
  the previous code. Compare in constant time.
* Success consumes the challenge and creates a session under a NEW token: the
  challenge cookie value is never a session token.
* Audit rows for addresses that are not admins carry only an HMAC of the
  address and its length, never what was typed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, List, Optional

from common.utils.client_ip import rate_limit_key
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.portal_config import PortalSettings
from backend.admin.repositories import sessions as repo
from backend.admin.security.clock import Clock
from backend.admin.security.keycheck import require_key
from backend.admin.security.mailer import AdminMailer
from backend.admin.security.ratelimit import Limiter, Rule, normalise_email
from backend.admin.services import audit
from backend.admin.services.sessions import SessionService

log = logging.getLogger("backend.admin.signin")

CODE_DIGITS = 8
MAX_EMAIL = 320
# one audit row per address window for requests refused by the address limit
BLOCKED_AUDIT = Rule("blocked_audit", 1, 600)
_DUMMY_SUBJECT = "nobody@invalid"
_DUMMY_DIGEST = hashlib.sha256(b"bettercollected/admin/signin/dummy").digest()

AfterResponse = Callable[[], Awaitable[object]]


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def normalise_code(raw: Optional[str]) -> Optional[str]:
    """The 8 digits of ``raw`` (spaces and hyphens ignored), or None."""
    text = "".join(ch for ch in str(raw or "") if ch not in " -\t")
    if len(text) == CODE_DIGITS and text.isascii() and text.isdigit():
        return text
    return None


@dataclass
class CodeRequest:
    cookie: str  # value for the challenge cookie (same shape for every address)
    after: List[AfterResponse] = field(default_factory=list)  # run in the background


@dataclass
class CodeCheck:
    session_token: Optional[str]
    after: List[AfterResponse] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.session_token is not None


class SignInService:
    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        settings: PortalSettings,
        limiter: Limiter,
        mailer: AdminMailer,
        sessions: SessionService,
        pepper: bytes,
        cookie_key: bytes,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._settings = settings
        self._limiter = limiter
        self._mailer = mailer
        self._sessions = sessions
        self._pepper = require_key(pepper, "sign-in pepper")
        self._cookie_key = require_key(cookie_key, "challenge cookie key")

    # -- primitives ------------------------------------------------------------
    def _code_digest(self, challenge_id: str, code: str) -> bytes:
        return hmac.new(
            self._pepper, f"{challenge_id}|{code}".encode(), hashlib.sha256
        ).digest()

    def _email_digest(self, email: str) -> str:
        return hmac.new(
            self._pepper, b"email|" + normalise_email(email).encode(), hashlib.sha256
        ).hexdigest()

    def _cookie_for(self, challenge_id: str, issued: int) -> str:
        """``<challenge id>.<issued at, epoch seconds>.<mac>``. The issue time is
        signed into the cookie so every challenge, real or not, has one fixed
        expiry the attempt counter is keyed on."""
        label = f"{challenge_id}.{issued}"
        mac = hmac.new(self._cookie_key, label.encode(), hashlib.sha256).digest()
        return f"{label}.{_b64(mac)}"

    def parse_cookie(self, cookie: Optional[str]) -> Optional[tuple]:
        """``(challenge id, issued at)`` of a cookie we signed, else None."""
        if not isinstance(cookie, str) or len(cookie) > 160:
            return None
        parts = cookie.split(".")
        if len(parts) != 3 or not parts[1].isascii() or not parts[1].isdigit():
            return None
        try:
            challenge_id = uuid.UUID(parts[0])
        except ValueError:
            return None
        if str(challenge_id) != parts[0]:
            return None
        issued = int(parts[1])
        expected = self._cookie_for(parts[0], issued).rpartition(".")[2]
        if not hmac.compare_digest(expected.encode(), parts[2].encode("utf-8", "replace")):
            return None
        return challenge_id, issued

    def _dead_cookie(self, ip: Optional[str]) -> str:
        """One fixed cookie per address window for requests that get no
        challenge because the address is over its limit: same shape as a real
        one, but the same value each time, so the number of ids an address can
        make us track stays bounded."""
        ttl = self._settings.code_ttl_seconds
        start = int(self._clock.time() // ttl) * ttl
        raw = hmac.new(
            self._cookie_key, f"dead|{rate_limit_key(ip)}|{start}".encode(), hashlib.sha256
        ).digest()[:16]
        return self._cookie_for(str(uuid.UUID(bytes=raw, version=4)), start)

    def _admin_list(self) -> List[str]:
        return sorted(self._settings.admin_emails)

    # -- step 1: request a code ------------------------------------------------
    async def request_code(
        self,
        email: str,
        ip: Optional[str],
        user_agent: Optional[str],
        request_id: Optional[str] = None,
    ) -> CodeRequest:
        email = normalise_email(email)[: MAX_EMAIL + 1]
        now = self._clock.now()
        decision = await self._limiter.request_code(email, ip)  # counts every address
        paused = (await self._limiter.sign_in_pause()).paused
        listed = len(email) <= MAX_EMAIL and self._settings.is_admin(email)
        issue = listed and decision.allowed and not paused

        challenge_id = uuid.uuid4()
        code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
        digest = self._code_digest(str(challenge_id), code)  # same work for everyone
        cookie = self._cookie_for(str(challenge_id), int(self._clock.time()))
        after: List[AfterResponse] = []

        if decision.blocked_by_ip:
            # over the per-address limit: nothing is issued or counted per email, and
            # only the first such request per window leaves an audit row, so a flood
            # cannot grow the tables. The same for every email, admin or not.
            cookie = self._dead_cookie(ip)
            first = await self._limiter.hit(BLOCKED_AUDIT, self._limiter.ip_key(ip))
            if first.allowed:
                async with self._engine.begin() as conn:
                    await audit.write(
                        conn, "signin.code_requested", None, None, None, None,
                        "denied", actor_kind="anonymous", ip=ip, ua=user_agent,
                        request_id=request_id, detail={"reason": "address_limited"},
                    )
            return CodeRequest(cookie, after)

        async with self._engine.begin() as conn:
            if issue:
                await repo.kill_open_challenges(conn, email, now)
                await repo.insert_challenge(
                    conn,
                    id=challenge_id,
                    email=email,
                    code_hash=digest,
                    ip=ip,
                    created_at=now,
                    expires_at=now + timedelta(seconds=self._settings.code_ttl_seconds),
                )
                await audit.write(
                    conn, "signin.code_requested", "challenge", str(challenge_id),
                    None, None, "success", actor_kind="anonymous", actor_email=email,
                    ip=ip, ua=user_agent, request_id=request_id,
                )
            else:
                await repo.kill_open_challenges(conn, _DUMMY_SUBJECT, now)  # no rows
                await repo.get_challenge(conn, challenge_id)  # stands for the insert
                reason = (
                    "rate_limited" if listed and not decision.allowed
                    else "paused" if listed and paused
                    else "not_admin"
                )
                await audit.write(
                    conn, "signin.code_requested", None, None, None, None, "denied",
                    actor_kind="anonymous",
                    actor_email=email if listed else None,
                    ip=ip, ua=user_agent, request_id=request_id,
                    detail=(
                        {"reason": reason}
                        if listed
                        else {
                            "reason": reason,
                            "email_hmac": self._email_digest(email),
                            "email_len": len(email),
                        }
                    ),
                )
        if issue:
            after.append(lambda: self._mailer.send_sign_in_code(email, code, ip or "unknown"))
        return CodeRequest(cookie, after)

    # -- step 2: check the code ------------------------------------------------
    async def verify_code(
        self,
        cookie: Optional[str],
        raw_code: Optional[str],
        ip: Optional[str],
        user_agent: Optional[str],
        request_id: Optional[str] = None,
    ) -> CodeCheck:
        """Check a code. For a cookie we signed, an admin's challenge and one that
        leads nowhere run the same sequence of database operations (selects,
        counter updates, audit rows), so neither time nor query count tells them
        apart; only mail and the success path differ, and a non-admin challenge
        can never reach success."""
        code = normalise_code(raw_code)
        parsed = self.parse_cookie(cookie)
        guess = code or "00000000"
        if parsed is None:  # not a cookie we issued: cheap refusal, nothing counted
            self._code_digest("none", guess)
            return CodeCheck(None)
        challenge_id, issued = parsed
        now = self._clock.now()
        ttl = self._settings.code_ttl_seconds
        if not issued - 60 <= self._clock.time() <= issued + ttl + 60:
            self._code_digest("none", guess)  # long expired (or from the future): refuse cheaply
            return CodeCheck(None)
        async with self._engine.connect() as conn:
            row = await repo.get_challenge(conn, challenge_id)
        listed = row is not None and row.email is not None and self._settings.is_admin(row.email)
        # a throwaway lock/failure key per challenge for everything that is not an admin's
        subject = row.email if listed else f"nobody-{challenge_id}@invalid"
        counter_expiry = datetime.fromtimestamp(issued + ttl, timezone.utc)
        email = row.email if listed else None
        after: List[AfterResponse] = []

        # limiter order: breaker pause, email lock, per-challenge attempts
        pause = await self._limiter.sign_in_pause()
        lock = await self._limiter.lock_status(subject)
        attempt = await self._limiter.challenge_attempt(str(challenge_id), counter_expiry)
        refused = pause.paused or lock.locked or not attempt.allowed
        if refused:
            async with self._engine.begin() as conn:
                if not attempt.allowed:
                    await repo.burn_challenge(conn, challenge_id, now)
                await self._audit_code(
                    conn, "signin.code_failed", "denied", challenge_id, email, ip,
                    user_agent, request_id,
                    "paused" if pause.paused else "locked" if lock.locked else "attempts",
                )
            return CodeCheck(None)

        usable = (
            listed
            and code is not None
            and row.consumed_at is None
            and row.expires_at > now
        )
        stored = bytes(row.code_hash) if usable else _DUMMY_DIGEST
        match = hmac.compare_digest(self._code_digest(str(challenge_id), guess), stored)

        if match and usable:
            async with self._engine.begin() as conn:
                if await repo.consume_challenge(conn, challenge_id, now):
                    token, session = await self._sessions.create(
                        row.email, ip, user_agent, request_id=request_id, conn=conn
                    )
                    await self._audit_code(
                        conn, "signin.code_verified", "success", challenge_id,
                        row.email, ip, user_agent, request_id, None, session.id,
                    )
                else:
                    token = None
            if token is not None:
                await self._limiter.record_success(row.email)
                return CodeCheck(token)

        # wrong, expired, reused or unknown: the same operations either way
        async with self._engine.begin() as conn:
            await repo.add_failed_attempt(conn, challenge_id)  # no row: no effect
            await self._audit_code(
                conn, "signin.code_failed", "failure", challenge_id, email, ip,
                user_agent, request_id, "wrong_or_unusable",
            )
        failure = await self._limiter.record_failure(subject)
        breaker = (
            await self._limiter.record_global_failure(ip, True)
            if listed
            else await self._limiter.decoy_global_failure(ip)
        )
        if failure.newly_locked:
            minutes = max(1, failure.retry_after // 60)
            async with self._engine.begin() as conn:
                await audit.write(
                    conn, "signin.locked", "account", None, None, None, "denied",
                    actor_kind="system", actor_email=email, ip=ip,
                    request_id=request_id, detail={"minutes": minutes},
                )
            if listed:
                after.append(
                    lambda: self._mailer.notify_lockout(
                        self._admin_list(), row.email, ip or "unknown", minutes
                    )
                )
        if breaker.newly_tripped:
            minutes = max(1, breaker.retry_after // 60)
            async with self._engine.begin() as conn:
                await audit.write(
                    conn, "signin.breaker_tripped", "service", None, None, None,
                    "denied", actor_kind="system", ip=ip, request_id=request_id,
                    detail={"minutes": minutes},
                )
            after.append(
                lambda: self._mailer.notify_lockout(
                    self._admin_list(), "the admin portal (all accounts)",
                    ip or "unknown", minutes,
                )
            )
        return CodeCheck(None, after)

    async def _audit_code(
        self, conn, action, outcome, challenge_id, email, ip, ua, request_id,
        reason, session_id=None,
    ) -> None:
        await audit.write(
            conn, action, "challenge", str(challenge_id), None, None, outcome,
            actor_kind="anonymous", actor_email=email, session_id=session_id,
            ip=ip, ua=ua, request_id=request_id,
            detail={"reason": reason} if reason else None,
        )
