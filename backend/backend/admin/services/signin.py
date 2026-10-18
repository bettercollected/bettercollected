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
from datetime import timedelta
from typing import Awaitable, Callable, List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.portal_config import PortalSettings
from backend.admin.repositories import sessions as repo
from backend.admin.security.clock import Clock
from backend.admin.security.keycheck import require_key
from backend.admin.security.mailer import AdminMailer
from backend.admin.security.ratelimit import Limiter, normalise_email
from backend.admin.services import audit
from backend.admin.services.sessions import SessionService

log = logging.getLogger("backend.admin.signin")

CODE_DIGITS = 8
MAX_EMAIL = 320
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

    def _cookie_for(self, challenge_id: str) -> str:
        mac = hmac.new(self._cookie_key, challenge_id.encode(), hashlib.sha256).digest()
        return f"{challenge_id}.{_b64(mac)}"

    def challenge_id_from_cookie(self, cookie: Optional[str]) -> Optional[uuid.UUID]:
        """The challenge id in a cookie we signed, else None."""
        if not isinstance(cookie, str) or len(cookie) > 128 or "." not in cookie:
            return None
        raw_id, _, mac = cookie.partition(".")
        try:
            challenge_id = uuid.UUID(raw_id)
        except ValueError:
            return None
        if str(challenge_id) != raw_id:
            return None
        expected = self._cookie_for(raw_id).partition(".")[2]
        if not hmac.compare_digest(expected.encode(), mac.encode("utf-8", "replace")):
            return None
        return challenge_id

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
        cookie = self._cookie_for(str(challenge_id))
        after: List[AfterResponse] = []

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
        code = normalise_code(raw_code)
        challenge_id = self.challenge_id_from_cookie(cookie)
        guess = code or "00000000"
        if challenge_id is None:  # not a cookie we issued: cheap refusal, nothing counted
            self._code_digest("none", guess)
            return CodeCheck(None)

        now = self._clock.now()
        async with self._engine.connect() as conn:
            row = await repo.get_challenge(conn, challenge_id)
        listed = row is not None and row.email is not None and self._settings.is_admin(row.email)
        subject = row.email if listed else _DUMMY_SUBJECT
        expires_at = row.expires_at if row is not None else now + timedelta(
            seconds=self._settings.code_ttl_seconds
        )
        after: List[AfterResponse] = []

        # limiter order: breaker pause, email lock, per-challenge attempts
        pause = await self._limiter.sign_in_pause()
        lock = await self._limiter.lock_status(subject)
        attempt = await self._limiter.challenge_attempt(str(challenge_id), expires_at)
        refused = pause.paused or lock.locked or not attempt.allowed
        if refused:
            async with self._engine.begin() as conn:
                if not attempt.allowed and row is not None:
                    await repo.burn_challenge(conn, challenge_id, now)
                await self._audit_code(
                    conn, "signin.code_failed", "denied", challenge_id,
                    row.email if listed else None, ip, user_agent, request_id,
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

        # wrong, expired, reused or unknown
        async with self._engine.begin() as conn:
            if row is not None:
                await repo.add_failed_attempt(conn, challenge_id)
            await self._audit_code(
                conn, "signin.code_failed", "failure", challenge_id,
                row.email if listed else None, ip, user_agent, request_id,
                "wrong_or_unusable",
            )
        failure = await self._limiter.record_failure(subject) if listed else None
        breaker = await self._limiter.record_global_failure(ip, listed)
        if failure is not None and failure.newly_locked:
            minutes = max(1, failure.retry_after // 60)
            async with self._engine.begin() as conn:
                await audit.write(
                    conn, "signin.locked", "account", None, None, None, "denied",
                    actor_kind="system", actor_email=row.email, ip=ip,
                    request_id=request_id, detail={"minutes": minutes},
                )
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
