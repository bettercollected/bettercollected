"""The authenticator-app second factor of an account (docs/totp.md).

Per account: at most one confirmed TOTP factor and one pending one, and ten
one-time recovery codes. This service enrols, confirms, checks a code,
regenerates the recovery codes and turns the factor off. It does not decide
where a second factor is asked for (sign-in, a workspace policy): callers use
:meth:`MfaService.check_code` for that.

Guessing is limited before a code is evaluated, not after: five evaluations per
five minutes per account however many arrive in parallel (``admit`` counts and
judges in one locked step), shared by the enrolment, the sign-in step and the
recovery codes so none is a second way to guess; a correct code gives its slot
back; the fifth wrong one locks the second-factor step for fifteen minutes. A
wrong code also counts against the client's address. Nothing here puts a code,
a secret or an address into a log line, an audit row or an error.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import List, Optional

import segno
from common.records import RecordId
from common.security.clock import Clock, SystemClock
from common.security.recovery import CODE_COUNT, generate_code, is_well_formed
from common.security.totp import generate_secret, otpauth_uri, verify
from fastapi_camelcase import CamelModel

from backend.app.exceptions import HTTPException
from backend.app.schemas.user_totp import (
    ENROLLED_RECENT_SIGN_IN,
    UserTotpFactorDocument,
)
from backend.app.schemas.workspace_audit_event import (
    NO_WORKSPACE,
    TOTP_ENROLLED,
    TOTP_LOCKED,
    TOTP_RECOVERY_REGENERATED,
    TOTP_RECOVERY_USED,
    TOTP_REMOVED,
    WorkspaceAuditEventDocument,
)
from backend.app.services.mfa.sealing import (
    hash_recovery_code,
    seal_secret,
    unseal_secret,
)
from backend.app.services.registration.secrets import SecretUnreadable
from backend.app.services.session_service import RevokeReason, aware

log = logging.getLogger(__name__)

# a session this young may add a factor without proving itself again (a stolen
# cookie of an older session cannot plant its own authenticator)
RECENT_SIGN_IN = dt.timedelta(minutes=15)
# a factor being set up that is not confirmed by then is replaced by the next
# start and purged by the daily job
PENDING_LIFETIME = dt.timedelta(minutes=15)
PENDING_PURGE_AFTER = dt.timedelta(hours=1)

# five evaluated guesses per five minutes per account
GUESS_SCOPE = "totp_guess"
GUESS_LIMIT = 5
GUESS_WINDOW_SECONDS = 300
# the fifth wrong one locks the second-factor step
LOCK_FOR = dt.timedelta(minutes=15)
# wrong codes per client address
ADDRESS_SCOPE = "totp_address"
ADDRESS_LIMIT = 20
ADDRESS_WINDOW_SECONDS = 600

TOTP_METHOD = "totp"
RECOVERY_METHOD = "recovery"

OFF_CODE = "totp_off"
OFF_MESSAGE = "Authenticator apps are not turned on on this instance."


class MfaStatusDto(CamelModel):
    # the switch is on: the second factor can be set up and is asked for
    available: bool
    # the account has a confirmed factor
    enabled: bool
    recovery_left: Optional[int] = None


class EnrolDto(CamelModel):
    """Shown once, when enrolment starts: the secret (grouped, for typing in),
    the provisioning address and its QR code as an inline SVG image."""

    factor_id: str
    secret: str
    uri: str
    qr: str


class RecoveryCodesDto(CamelModel):
    """Shown once: the only time the codes exist in clear."""

    recovery_codes: List[str]


@dataclass(frozen=True)
class Verified:
    """A second factor that was just accepted."""

    method: str  # TOTP_METHOD or RECOVERY_METHOD
    recovery_left: Optional[int] = None


def totp_enabled() -> bool:
    from backend.config import settings

    return bool(settings.totp.ENABLED)


def _refused(status: HTTPStatus, code: str, message: str, **extra) -> HTTPException:
    headers = None
    if "retry_after" in extra:
        headers = {"Retry-After": str(extra["retry_after"])}
    return HTTPException(
        status, content={"code": code, "message": message, **extra}, headers=headers
    )


def refuse_when_off() -> None:
    if not totp_enabled():
        raise _refused(HTTPStatus.UNPROCESSABLE_ENTITY, OFF_CODE, OFF_MESSAGE)


def invalid_code() -> HTTPException:
    # one answer for every wrong, replayed, expired or malformed code
    return _refused(
        HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_code", "That code is not valid."
    )


def _group(secret: str) -> str:
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


def qr_data_uri(uri: str) -> str:
    """The provisioning address as an SVG image (a data address: nothing is
    fetched, the SVG holds no script and no link)."""
    return segno.make(uri, error="m").svg_data_uri(scale=4, border=2)


class MfaService:
    def __init__(
        self,
        factor_repo,
        session_repo,
        session_service,
        rate_limiter,
        crypto,
        audit_repo=None,
        clock: Optional[Clock] = None,
        issuer: Optional[str] = None,
    ):
        self._factors = factor_repo
        self._sessions = session_repo
        self._session_service = session_service
        self._limiter = rate_limiter
        self._crypto = crypto
        self._audit = audit_repo
        self._clock = clock or SystemClock()
        self._issuer = issuer

    def _now(self) -> dt.datetime:
        return self._clock.now()

    # -- status ----------------------------------------------------------------
    async def status(self, user) -> MfaStatusDto:
        if not totp_enabled():
            return MfaStatusDto(available=False, enabled=False)
        factor = await self._factors.confirmed(user.id)
        if factor is None:
            return MfaStatusDto(available=True, enabled=False)
        return MfaStatusDto(
            available=True,
            enabled=True,
            recovery_left=await self._factors.codes_left(user.id),
        )

    # -- enrolment -------------------------------------------------------------
    async def begin_enrolment(
        self, user, current_code: Optional[str] = None, client: Optional[str] = None
    ) -> EnrolDto:
        """Start setting up an authenticator app: a new pending factor (any
        earlier pending one is dropped) and what the app needs. Needs a session
        no older than ``RECENT_SIGN_IN``; an account that already has a factor
        also presents a current code in the same request (replacing it is as
        sensitive as turning it off)."""
        refuse_when_off()
        await self._require_recent_sign_in(user)
        if await self._factors.confirmed(user.id) is not None:
            await self.check_code(user, current_code, client)
        secret = generate_secret()
        factor_id = RecordId()
        factor = UserTotpFactorDocument(
            id=factor_id,
            user_id=str(user.id),
            secret_sealed=seal_secret(self._crypto, user.id, factor_id, secret),
        )
        await self._factors.replace_pending(factor)
        uri = otpauth_uri(secret, user.sub, self._issuer or _issuer())
        return EnrolDto(
            factor_id=str(factor.id),
            secret=_group(secret),
            uri=uri,
            qr=qr_data_uri(uri),
        )

    async def confirm_enrolment(
        self,
        user,
        factor_id: str,
        code: str,
        client: Optional[str] = None,
    ) -> RecoveryCodesDto:
        """Make the pending factor the account's one factor, if ``code`` is
        right: in one transaction, with the recovery codes. The session that
        did it counts as having presented the factor."""
        refuse_when_off()
        now = self._now()
        pending = await self._factors.pending(user.id)
        if (
            pending is None
            or str(pending.id) != str(factor_id)
            or aware(pending.created_at) + PENDING_LIFETIME < now
        ):
            # replaced, expired or never started: the same answer as a wrong code
            raise invalid_code()
        await self._gate(user.id, client)
        verdict = await self._limiter.admit(
            GUESS_SCOPE, str(user.id), GUESS_LIMIT, GUESS_WINDOW_SECONDS
        )
        if not verdict.allowed:
            raise self._too_many(verdict.retry_after)
        step = None
        try:
            secret = unseal_secret(
                self._crypto, user.id, pending.id, pending.secret_sealed
            )
            step = verify(secret, code, self._clock)
        except SecretUnreadable:
            log.error("totp: a pending factor could not be opened")
        if step is None:
            await self._count_wrong_code(client)
            raise invalid_code()
        await self._limiter.release(GUESS_SCOPE, str(user.id), GUESS_WINDOW_SECONDS)
        codes = [generate_code() for _ in range(CODE_COUNT)]
        stored = await self._factors.confirm(
            str(user.id),
            str(pending.id),
            step,
            [hash_recovery_code(user.id, c) for c in codes],
            now,
            enrolled_via=ENROLLED_RECENT_SIGN_IN,
        )
        if not stored:
            raise invalid_code()
        if user.sid:
            await self._sessions.set_mfa(user.sid, str(user.id), now, TOTP_METHOD)
        await self._record(TOTP_ENROLLED, user.id, user.sid)
        return RecoveryCodesDto(recovery_codes=codes)

    # -- using the factor ------------------------------------------------------
    async def check_code(
        self, user, code: Optional[str], client: Optional[str] = None
    ) -> Verified:
        """Accept ``code`` (an authenticator code or a recovery code) for the
        account's confirmed factor, or raise: 409 ``no_factor``, 429
        ``mfa_locked`` / ``too_many_attempts``, 422 ``invalid_code``. What
        sign-in, the step-up and every sensitive change call."""
        refuse_when_off()
        return await self._check(str(user.id), code, client, user.sid)

    async def _check(
        self,
        user_id: str,
        code: Optional[str],
        client: Optional[str],
        session_id: Optional[str],
    ) -> Verified:
        factor = await self._factors.confirmed(user_id)
        if factor is None:
            raise _refused(
                HTTPStatus.CONFLICT, "no_factor", "No authenticator app is set up."
            )
        now = self._now()
        if factor.locked_until is not None and factor.locked_until > now:
            raise _refused(
                HTTPStatus.TOO_MANY_REQUESTS,
                "mfa_locked",
                "Too many attempts. Try again later.",
                retry_after=max(1, int((factor.locked_until - now).total_seconds())),
            )
        await self._gate(user_id, client)
        verdict = await self._limiter.admit(
            GUESS_SCOPE, user_id, GUESS_LIMIT, GUESS_WINDOW_SECONDS
        )
        if not verdict.allowed:
            raise self._too_many(verdict.retry_after)
        method = await self._match(user_id, factor, code, now)
        if method is not None:
            await self._limiter.release(GUESS_SCOPE, user_id, GUESS_WINDOW_SECONDS)
            if method == RECOVERY_METHOD:
                await self._record(TOTP_RECOVERY_USED, user_id, session_id)
                return Verified(method, await self._factors.codes_left(user_id))
            return Verified(method)
        await self._count_wrong_code(client)
        if verdict.count >= GUESS_LIMIT:
            await self._lock(factor, now, session_id)
        raise invalid_code()

    async def _match(
        self, user_id: str, factor, code: Optional[str], now: dt.datetime
    ) -> Optional[str]:
        """``TOTP_METHOD`` / ``RECOVERY_METHOD`` when ``code`` is a valid,
        unused one (and spends it), else None. Never raises on a malformed
        code."""
        raw = "" if code is None else str(code)
        if is_well_formed(raw):
            burned = await self._factors.burn_code(
                user_id, hash_recovery_code(user_id, raw), now
            )
            return RECOVERY_METHOD if burned else None
        try:
            secret = unseal_secret(
                self._crypto, user_id, factor.id, factor.secret_sealed
            )
        except SecretUnreadable:
            log.error("totp: a confirmed factor could not be opened")
            return None
        step = verify(secret, raw, self._clock)
        if step is None or not await self._factors.accept_step(str(factor.id), step):
            return None
        return TOTP_METHOD

    async def _lock(self, factor, now: dt.datetime, session_id) -> None:
        if await self._factors.lock(str(factor.id), now + LOCK_FOR, now):
            await self._record(TOTP_LOCKED, factor.user_id, session_id)

    async def _gate(self, user_id: str, client: Optional[str]) -> None:
        """Refuse a client address that has sent too many wrong codes."""
        if not client:
            return
        verdict = await self._limiter.hit(
            ADDRESS_SCOPE, client, ADDRESS_LIMIT, ADDRESS_WINDOW_SECONDS, amount=0
        )
        if verdict.count >= ADDRESS_LIMIT:
            raise self._too_many(verdict.retry_after)

    async def _count_wrong_code(self, client: Optional[str]) -> None:
        if client:
            await self._limiter.hit(
                ADDRESS_SCOPE, client, ADDRESS_LIMIT, ADDRESS_WINDOW_SECONDS
            )

    @staticmethod
    def _too_many(retry_after: int) -> HTTPException:
        return _refused(
            HTTPStatus.TOO_MANY_REQUESTS,
            "too_many_attempts",
            "Too many attempts. Try again later.",
            retry_after=retry_after,
        )

    async def step_up(
        self, user, code: Optional[str], client: Optional[str] = None
    ) -> MfaStatusDto:
        """Present the second factor in the session that is already signed in
        (what a workspace that requires one asks for): the session records it."""
        verified = await self.check_code(user, code, client)
        if user.sid:
            await self._sessions.set_mfa(
                user.sid, str(user.id), self._now(), verified.method
            )
        return await self.status(user)

    # -- sensitive changes -----------------------------------------------------
    async def regenerate_recovery_codes(
        self, user, code: Optional[str], client: Optional[str] = None
    ) -> RecoveryCodesDto:
        """A fresh code in the same request; the old recovery codes stop
        working at once."""
        await self.check_code(user, code, client)
        factor = await self._factors.confirmed(user.id)
        codes = [generate_code() for _ in range(CODE_COUNT)]
        if factor is None or not await self._factors.replace_codes(
            str(user.id),
            str(factor.id),
            [hash_recovery_code(user.id, c) for c in codes],
        ):
            raise _refused(
                HTTPStatus.CONFLICT, "no_factor", "No authenticator app is set up."
            )
        await self._record(TOTP_RECOVERY_REGENERATED, user.id, user.sid)
        return RecoveryCodesDto(recovery_codes=codes)

    async def disable(
        self, user, code: Optional[str], client: Optional[str] = None
    ) -> MfaStatusDto:
        """Turn the account's factor off (a fresh code in the same request).
        The account's other sessions end."""
        await self.check_code(user, code, client)
        await self._factors.delete_for_user(str(user.id))
        await self._record(TOTP_REMOVED, user.id, user.sid)
        await self._session_service.revoke_all_for_user(
            str(user.id), RevokeReason.MFA_RESET, except_sid=user.sid
        )
        return await self.status(user)

    # -- housekeeping ----------------------------------------------------------
    async def delete_for_account(self, user_id: str) -> int:
        """The account is gone: its factors and recovery codes go with it."""
        return await self._factors.delete_for_user(str(user_id))

    async def purge_pending(self) -> int:
        """The daily purge: factors set up and never confirmed."""
        return await self._factors.purge_pending(self._now() - PENDING_PURGE_AFTER)

    # -- helpers ---------------------------------------------------------------
    async def _require_recent_sign_in(self, user) -> None:
        session = await self._sessions.get(user.sid) if user.sid else None
        created = aware(session.created_at) if session is not None else None
        if created is None or self._now() - created > RECENT_SIGN_IN:
            raise _refused(
                HTTPStatus.FORBIDDEN,
                "recent_proof_required",
                "Sign in again to set up an authenticator app.",
            )

    async def _record(self, event: str, user_id, session_id) -> None:
        """One audit entry, ids only; never refuses what was just done."""
        if self._audit is None:
            return
        try:
            await self._audit.record(
                WorkspaceAuditEventDocument(
                    id=RecordId(),
                    workspace_id=RecordId(NO_WORKSPACE),
                    user_id=str(user_id),
                    session_id=str(session_id) if session_id else None,
                    event=event,
                )
            )
        except Exception as error:  # noqa: BLE001 — the factor change stands
            log.error(
                "AUDIT %s NOT STORED user=%s session=%s (%s)",
                event,
                user_id,
                session_id,
                type(error).__name__,
            )


def _issuer() -> str:
    from backend.config import settings

    return settings.ORGANIZATION_NAME or "Better Collected"
