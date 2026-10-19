"""The second factor (TOTP) and its recovery codes.

* Enrolment: ``start_enrol`` stores a fresh 160-bit secret sealed with the
  ``admin/totp`` subkey (envelope v1, AAD ``factor_id|email``, so a blob moved to
  another row or address does not open) and returns the provisioning URI and a
  server-drawn QR. ``confirm_enrol`` accepts one valid code and, in the SAME
  transaction, confirms the factor, drops older ones, creates ten recovery codes
  (returned once, stored as keyed hashes), moves the session to ``mfa_ok`` under
  a new token and audits. Nothing is partly done.
* Verification (sign-in and step-up) takes a TOTP code or a recovery code. A TOTP
  step is accepted at most once (atomic ``last_used_step`` update); a recovery
  code is burned atomically, mails every admin and is audited.
* The limiter is wired as its docstrings say: breaker pause and lock are checked
  first (a refused attempt is not counted), a wrong code is a failure for the
  email and, as an identified admin, for the global breaker, and a new lockout or
  breaker trip mails every admin once.
* Every state change and its audit row share one transaction (fail closed).
* Guesses are reserved BEFORE the code is evaluated (``Limiter.factor_attempt``):
  at most five are evaluated per five minutes however many arrive in parallel; a
  correct code resets the reservation. A wrong code (in ``confirm_enrol`` too)
  counts as a failure; a request with no confirmed factor to guess at does not.
"""

from __future__ import annotations

import base64
import io
import logging
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Optional

import segno
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.admin.portal_config import PortalSettings
from backend.admin.repositories import factors as repo
from backend.admin.security import envelope, recovery, totp
from backend.admin.security.clock import Clock
from backend.admin.security.keycheck import require_key
from backend.admin.security.mailer import AdminMailer
from backend.admin.security.ratelimit import Limiter
from backend.admin.services import audit
from backend.admin.services.sessions import Session, SessionService

log = logging.getLogger("backend.admin.factors")

KEY_ID = "totp1"
AfterResponse = Callable[[], Awaitable[object]]

# refusal reasons (internal; pages show one generic text per kind)
LOCKED = "locked"
PAUSED = "paused"
WRONG = "wrong"
NO_FACTOR = "no_factor"
NOT_ALLOWED = "not_allowed"
STEPUP_REQUIRED = "stepup_required"
STALE = "stale"


class _Rollback(Exception):
    """Undo the open transaction; nothing was accepted."""


def qr_data_uri(uri: str) -> str:
    """The provisioning URI as an inline SVG data URI. Drawn locally by segno;
    nothing is fetched and the SVG carries no scripts or links."""
    out = io.BytesIO()
    segno.make(uri, error="m").save(
        out, kind="svg", scale=5, border=2, xmldecl=False, svgns=True, nl=False
    )
    return "data:image/svg+xml;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def group4(text: str) -> str:
    return " ".join(text[i : i + 4] for i in range(0, len(text), 4))


@dataclass
class EnrolStart:
    factor_id: uuid.UUID
    secret: str  # base32, grouped for typing into an app by hand
    uri: str
    qr: str  # data URI
    after: List[AfterResponse] = field(default_factory=list)  # mail jobs of the code check


@dataclass
class Outcome:
    ok: bool
    reason: Optional[str] = None
    retry_minutes: int = 0
    new_token: Optional[str] = None
    method: Optional[str] = None  # "totp" | "recovery"
    codes: List[str] = field(default_factory=list)  # shown once
    after: List[AfterResponse] = field(default_factory=list)


@dataclass(frozen=True)
class FactorStatus:
    confirmed: bool
    recovery_left: int


class FactorService:
    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        settings: PortalSettings,
        limiter: Limiter,
        mailer: AdminMailer,
        sessions: SessionService,
        pepper: bytes,
        totp_key: bytes,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._settings = settings
        self._limiter = limiter
        self._mailer = mailer
        self._sessions = sessions
        self._pepper = require_key(pepper, "recovery pepper")
        self._key = require_key(totp_key, "TOTP key")

    # -- helpers ---------------------------------------------------------------
    def _admins(self) -> List[str]:
        return sorted(self._settings.admin_emails)

    @staticmethod
    def _aad(factor_id, email: str) -> bytes:
        return f"{factor_id}|{email}".encode("utf-8")

    def _seal(self, secret: str, factor_id, email: str) -> str:
        return envelope.encrypt(secret.encode("ascii"), self._key, KEY_ID, self._aad(factor_id, email))

    def _open(self, blob: str, factor_id, email: str) -> Optional[str]:
        try:
            return envelope.decrypt(blob, self._key, self._aad(factor_id, email)).decode("ascii")
        except (envelope.EnvelopeError, UnicodeDecodeError):
            log.error("a factor secret could not be opened")  # no ids, no values
            return None

    async def _audit(
        self, conn: AsyncConnection, action: str, outcome: str, session: Optional[Session],
        email: str, ip, ua, request_id, target_id=None, detail=None,
        actor_kind: str = "admin",
    ) -> None:
        await audit.write(
            conn, action, "factor", None if target_id is None else str(target_id),
            None, None, outcome, actor_kind=actor_kind, actor_email=email,
            session_id=session.id if session else None, ip=ip, ua=ua,
            request_id=request_id, detail=detail,
        )

    async def status(self, email: str) -> FactorStatus:
        async with self._engine.connect() as conn:
            factor = await repo.get_confirmed(conn, email)
            left = await repo.count_unused(conn, factor.id) if factor else 0
        return FactorStatus(factor is not None, left)

    # -- limiter wiring --------------------------------------------------------
    async def _refusal(self, email: str) -> Optional[tuple]:
        """``(reason, minutes)`` while the breaker pauses sign-in, the email is
        locked or its guesses for this window are used up; such an attempt is
        refused before any code is looked at. Otherwise it reserves one guess."""
        pause = await self._limiter.sign_in_pause()
        if pause.paused:
            return PAUSED, max(1, pause.retry_after // 60)
        lock = await self._limiter.lock_status(email)
        if lock.locked:
            return LOCKED, max(1, lock.retry_after // 60)
        attempt = await self._limiter.factor_attempt(email)  # reserves a guess, atomically
        if not attempt.allowed:
            return LOCKED, max(1, attempt.retry_after // 60)
        return None

    async def _refuse(self, reason, minutes, session, email, ip, ua, rid, action) -> Outcome:
        # No audit row: the lock and the breaker are audited once when they start,
        # and a refused attempt must not be a way to grow the log.
        return Outcome(False, reason, minutes)

    async def _after_failure(self, email: str, ip, rid) -> List[AfterResponse]:
        """Count a wrong code (email, then global breaker); lockout and trip
        notices go out once, as the limiter reports ``newly_*``."""
        after: List[AfterResponse] = []
        failure = await self._limiter.record_failure(email)
        breaker = await self._limiter.record_global_failure(ip, True)
        if failure.newly_locked:
            minutes = max(1, failure.retry_after // 60)
            async with self._engine.begin() as conn:
                await audit.write(
                    conn, "signin.locked", "account", None, None, None, "denied",
                    actor_kind="system", actor_email=email, ip=ip, request_id=rid,
                    detail={"minutes": minutes},
                )
            after.append(
                lambda: self._mailer.notify_lockout(self._admins(), email, ip or "unknown", minutes)
            )
        if breaker.newly_tripped:
            minutes = max(1, breaker.retry_after // 60)
            async with self._engine.begin() as conn:
                await audit.write(
                    conn, "signin.breaker_tripped", "service", None, None, None,
                    "denied", actor_kind="system", ip=ip, request_id=rid,
                    detail={"minutes": minutes},
                )
            after.append(
                lambda: self._mailer.notify_lockout(
                    self._admins(), "the admin portal (all accounts)", ip or "unknown", minutes
                )
            )
        return after

    # -- enrolment -------------------------------------------------------------
    def _may_enrol(self, session: Session, has_confirmed: bool) -> Optional[str]:
        """The policy: an ``email_ok`` session may enrol only while the admin has
        no confirmed factor; a signed-in one (add or replace) needs a fresh step-up."""
        if session.mfa_state == "mfa_ok":
            return None if self._sessions.stepup_fresh(session) else STEPUP_REQUIRED
        return NOT_ALLOWED if has_confirmed else None

    async def start_enrol(
        self, session: Session, ip, ua, rid, code: Optional[str] = None
    ) -> Outcome | EnrolStart:
        """Draw and store a new pending factor. Returns an ``Outcome`` (refused)
        or an ``EnrolStart``. A second start replaces the previous pending one.

        A signed-in session (adding or replacing a factor) must send a fresh
        factor ``code`` in this very request: the 300 s step-up window that
        sign-in itself opens is not enough, so a stolen session cookie alone
        cannot start a replacement."""
        email = session.email
        checked: List[AfterResponse] = []
        if session.mfa_state == "mfa_ok":
            fresh = await self.verify_stepup(session, code or "", ip, ua, rid)
            if not fresh.ok:
                return fresh
            checked = fresh.after
            reloaded = await self._sessions.reload(session)
            if reloaded is None:
                return Outcome(False, STALE)
            session = reloaded
        now = self._clock.now()
        async with self._engine.begin() as conn:
            await repo.lock_for_update(conn, email)
            confirmed = await repo.get_confirmed(conn, email)
            reason = self._may_enrol(session, confirmed is not None)
            if reason:  # policy refusals write nothing (no unthrottled log growth)
                return Outcome(False, reason)
            secret = totp.generate_secret()
            factor_id = uuid.uuid4()
            await repo.delete_pending(conn, email)
            await repo.insert_factor(conn, factor_id, email, self._seal(secret, factor_id, email), KEY_ID, now)
            await self._audit(
                conn, "mfa.enrol_started", "success", session, email, ip, ua, rid,
                target_id=factor_id,
            )
        uri = totp.otpauth_uri(secret, email, self._settings.totp_issuer)
        return EnrolStart(factor_id, group4(secret), uri, qr_data_uri(uri), checked)

    async def confirm_enrol(
        self, session: Session, session_token: str, factor_id: Optional[uuid.UUID],
        raw_code: str, ip, ua, rid,
    ) -> Outcome:
        email = session.email
        refused = await self._refusal(email)
        if refused:
            return await self._refuse(*refused, session, email, ip, ua, rid, "mfa.enrol_confirmed")
        now = self._clock.now()
        try:
            async with self._engine.begin() as conn:
                await repo.lock_for_update(conn, email)
                confirmed = await repo.get_confirmed(conn, email)
                reason = self._may_enrol(session, confirmed is not None)
                if reason:
                    return Outcome(False, reason)
                pending = None if factor_id is None else await repo.get_pending(conn, factor_id, email)
                if pending is None:
                    return Outcome(False, STALE)
                secret = self._open(pending.secret_blob, pending.id, email)
                step = totp.verify(secret, raw_code, self._clock) if secret else None
                if step is None:
                    await self._audit(
                        conn, "mfa.enrol_confirmed", "failure", session, email, ip, ua, rid,
                        target_id=pending.id, detail={"reason": "wrong_code"},
                    )
                    bad = True
                else:
                    bad = False
                    if not await repo.confirm(conn, pending.id, email, now, step):
                        raise _Rollback()  # another request confirmed it first
                    await repo.delete_confirmed_except(conn, email, pending.id)
                    issued = recovery.issue(self._pepper)
                    await repo.insert_recovery(
                        conn, pending.id, [bytes.fromhex(h) for h in issued.hashes], now
                    )
                    token = await self._sessions.promote_to_mfa(
                        session, session_token, ip, ua, rid, conn=conn
                    )
                    if token is None:
                        raise _Rollback()  # the session token is stale
                    await self._audit(
                        conn,
                        "mfa.replaced" if confirmed is not None else "mfa.enrolled",
                        "success", session, email, ip, ua, rid, target_id=pending.id,
                        detail={"issued": len(issued.hashes)},
                    )
        except _Rollback:
            return Outcome(False, STALE)
        if bad:
            return Outcome(False, WRONG, after=await self._after_failure(email, ip, rid))
        await self._limiter.record_success(email)
        return Outcome(
            True, new_token=token, method="totp", codes=issued.reveal(),
            after=[lambda: self._mailer.notify_enrolment(self._admins(), email, ip or "unknown")],
        )

    # -- verification ----------------------------------------------------------
    async def _match(self, conn: AsyncConnection, factor, raw: str, now) -> Optional[str]:
        """``"totp"`` or ``"recovery"`` when ``raw`` is a valid, unused code, with
        the replay guard / the burn already applied in ``conn``."""
        if recovery.is_well_formed(raw):
            hashes = await repo.unused_hashes(conn, factor.id)
            index = recovery.verify(self._pepper, raw, [h.hex() for h in hashes])
            if index is not None and await repo.burn_recovery(conn, hashes[index], now):
                return "recovery"
            return None
        secret = self._open(factor.secret_blob, factor.id, factor.email)
        step = totp.verify(secret, raw, self._clock) if secret else None
        if step is not None and await repo.advance_step(conn, factor.id, step):
            return "totp"
        return None

    async def _verify(
        self, session: Session, raw_code: str, ip, ua, rid, action: str,
        on_success: Callable[[AsyncConnection], Awaitable[object]],
    ) -> Outcome:
        email = session.email
        raw = str(raw_code or "")[:64]
        refused = await self._refusal(email)
        if refused:
            return await self._refuse(*refused, session, email, ip, ua, rid, action)
        now = self._clock.now()
        try:
            async with self._engine.begin() as conn:
                factor = await repo.get_confirmed(conn, email)
                if factor is None:
                    return Outcome(False, NO_FACTOR)
                method = await self._match(conn, factor, raw, now)
                if method is None:
                    await self._audit(
                        conn, action, "failure", session, email, ip, ua, rid,
                        target_id=factor.id, detail={"reason": WRONG},
                    )
                else:
                    payload = await on_success(conn)
                    if payload is False:
                        raise _Rollback()
                    detail = {"method": method}
                    left = await repo.count_unused(conn, factor.id)
                    if method == "recovery":
                        detail["recovery_left"] = left
                    new_address = False
                    if action == "mfa.verified":
                        known = await repo.recent_session_ips(conn, email, session.id)
                        new_address = bool(ip and known and ip not in known)
                        detail["new_address"] = new_address
                    await self._audit(
                        conn,
                        "mfa.recovery_used" if method == "recovery" else action,
                        "success", session, email, ip, ua, rid, target_id=factor.id,
                        detail=detail,
                    )
        except _Rollback:
            return Outcome(False, STALE)
        if method is None:
            return Outcome(False, WRONG, after=await self._after_failure(email, ip, rid))
        await self._limiter.record_success(email)
        after: List[AfterResponse] = []
        if method == "recovery":
            after.append(
                lambda: self._mailer.notify_recovery_use(self._admins(), email, ip or "unknown", left)
            )
        if new_address:
            after.append(
                lambda: self._mailer.notify_new_address(self._admins(), email, ip or "unknown")
            )
        return Outcome(True, method=method, new_token=payload if isinstance(payload, str) else None, after=after)

    async def verify_login(
        self, session: Session, session_token: str, raw_code: str, ip, ua, rid
    ) -> Outcome:
        """The second step of sign-in: on success the session becomes ``mfa_ok``
        under a NEW token (``new_token``) in the same transaction."""

        async def promote(conn):
            token = await self._sessions.promote_to_mfa(
                session, session_token, ip, ua, rid, conn=conn
            )
            return token if token is not None else False

        return await self._verify(session, raw_code, ip, ua, rid, "mfa.verified", promote)

    async def verify_stepup(self, session: Session, raw_code: str, ip, ua, rid) -> Outcome:
        """A fresh code for a sensitive action: starts a new step-up window."""

        async def mark(conn):
            await self._sessions.mark_stepup(session, conn=conn)
            return True

        return await self._verify(session, raw_code, ip, ua, rid, "mfa.stepup", mark)

    # -- recovery codes --------------------------------------------------------
    async def regenerate_codes(
        self, session: Session, raw_code: Optional[str], ip, ua, rid
    ) -> Outcome:
        """Replace all recovery codes (the old set stops working). Needs a fresh
        second-factor code sent with this request (not just the step-up window
        sign-in opens), and mails every admin; the new codes are in ``codes``
        once."""
        email = session.email
        fresh = await self.verify_stepup(session, raw_code or "", ip, ua, rid)
        if not fresh.ok:
            return fresh
        async with self._engine.begin() as conn:
            factor = await repo.get_confirmed(conn, email)
            if factor is None:
                return Outcome(False, NO_FACTOR)
            issued = recovery.issue(self._pepper)
            await repo.delete_recovery(conn, factor.id)
            await repo.insert_recovery(
                conn, factor.id, [bytes.fromhex(h) for h in issued.hashes], self._clock.now()
            )
            await self._audit(
                conn, "mfa.recovery_regenerated", "success", session, email, ip, ua, rid,
                target_id=factor.id, detail={"issued": len(issued.hashes)},
            )
        return Outcome(
            True, codes=issued.reveal(),
            after=fresh.after + [
                lambda: self._mailer.notify_recovery_regenerated(
                    self._admins(), email, ip or "unknown"
                )
            ],
        )

    # -- break glass -----------------------------------------------------------
    async def reset_factor(self, email: str, os_user: str) -> Outcome:
        """Operator command: remove every factor (and recovery code) of ``email``
        and revoke its sessions, audited as the CLI. Re-enrolment is then forced at
        the next email-code sign-in. Mails every admin after commit (``after``)."""
        email = email.strip().lower()
        async with self._engine.begin() as conn:
            removed = await repo.delete_all(conn, email)
            revoked = await self._sessions.revoke_all(
                email, by="cli", reason="factor_reset", actor_kind="cli", conn=conn
            )
            await audit.write(
                conn, "cli.reset_factor", "factor", None, None, None, "success",
                actor_kind="cli", actor_email=email,
                detail={"os_user": os_user, "factors": removed, "revoked": revoked},
            )
        return Outcome(
            True, after=[lambda: self._mailer.notify_factor_reset(self._admins(), email)]
        )
