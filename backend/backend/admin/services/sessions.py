"""Admin sessions: opaque tokens, expiry, binding, limits, revocation.

The cookie holds a 256-bit random token; the database only ever sees its
SHA-256. Every change that matters is written together with its audit row in
one transaction, so a failed audit write undoes the action (fail closed).

Policy lives here; SQL lives in ``repositories/sessions.py``.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Collection, Iterable, Optional

from common.utils.client_ip import rate_limit_key
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.admin.portal_config import PortalSettings
from backend.admin.repositories import sessions as repo
from backend.admin.security.clock import Clock
from backend.admin.services import audit

log = logging.getLogger("backend.admin.sessions")

TOUCH_INTERVAL_SECONDS = 60
STEPUP_MAX_AGE_SECONDS = 300
FINISHED_KEEP_DAYS = 7

# internal reasons; never shown to the client
OK = "ok"
UNKNOWN = "unknown"
REVOKED = "revoked"
IDLE = "idle_expired"
ABSOLUTE = "absolute_expired"
BINDING = "binding_mismatch"
NOT_ADMIN = "not_admin"
MFA_REQUIRED = "mfa_required"


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8", "replace")).digest()


def hash_user_agent(user_agent: Optional[str]) -> bytes:
    return hashlib.sha256((user_agent or "").encode("utf-8", "replace")).digest()


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


@dataclass(frozen=True)
class Session:
    id: uuid.UUID
    email: str
    mfa_state: str
    stepup_at: Optional[datetime]
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    abs_expires_at: datetime
    ip: Optional[str]

    @classmethod
    def from_row(cls, row) -> "Session":
        return cls(
            id=row.id,
            email=row.email,
            mfa_state=row.mfa_state,
            stepup_at=row.stepup_at,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            idle_expires_at=row.idle_expires_at,
            abs_expires_at=row.abs_expires_at,
            ip=str(row.ip) if row.ip is not None else None,
        )


@dataclass(frozen=True)
class AuthResult:
    session: Optional[Session]
    reason: str

    @property
    def ok(self) -> bool:
        return self.session is not None


class SessionService:
    def __init__(
        self, engine: AsyncEngine, clock: Clock, settings: PortalSettings
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._settings = settings

    # -- helpers ---------------------------------------------------------------
    def _idle(self, now: datetime, absolute: datetime) -> datetime:
        return min(now + timedelta(minutes=self._settings.idle_minutes), absolute)

    async def _audit(
        self,
        conn: AsyncConnection,
        action: str,
        outcome: str = "success",
        *,
        email: Optional[str] = None,
        session_id: Any = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
        request_id: Optional[str] = None,
        actor_kind: str = "admin",
        detail: Any = None,
    ) -> None:
        await audit.write(
            conn,
            action,
            "session",
            str(session_id) if session_id else None,
            None,
            None,
            outcome,
            actor_kind=actor_kind,
            actor_email=email,
            session_id=session_id,
            ip=ip,
            ua=ua,
            request_id=request_id,
            detail=detail,
        )

    async def _revoke_rows(
        self,
        conn: AsyncConnection,
        ids: Iterable[uuid.UUID],
        reason: str,
        by: Optional[str],
        *,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
        request_id: Optional[str] = None,
        actor_kind: str = "system",
        action: str = "session.revoked",
    ) -> int:
        changed = await repo.revoke(conn, list(ids), self._clock.now(), reason, by)
        for row in changed:
            await self._audit(
                conn,
                action,
                email=row.email,
                session_id=row.id,
                ip=ip,
                ua=ua,
                request_id=request_id,
                actor_kind=actor_kind,
                detail={"reason": reason},
            )
        return len(changed)

    # -- creation --------------------------------------------------------------
    async def create(
        self,
        email: str,
        ip: Optional[str],
        user_agent: Optional[str],
        *,
        mfa_state: str = "email_ok",
        request_id: Optional[str] = None,
        conn: Optional[AsyncConnection] = None,
    ) -> tuple[str, Session]:
        """A new session under a new random token. At most ``max_sessions``
        stay live per admin: the oldest are revoked. Pass ``conn`` to join the
        caller's transaction."""
        if conn is None:
            async with self._engine.begin() as own:
                return await self.create(
                    email, ip, user_agent, mfa_state=mfa_state,
                    request_id=request_id, conn=own,
                )
        email = email.strip().lower()
        now = self._clock.now()
        live = await repo.list_live(conn, email, now)
        excess = len(live) - (self._settings.max_sessions - 1)
        if excess > 0:
            await self._revoke_rows(
                conn,
                [row.id for row in live[:excess]],
                "session_limit",
                "system",
                ip=ip,
                ua=user_agent,
                request_id=request_id,
            )
        token = new_token()
        absolute = now + timedelta(hours=self._settings.absolute_hours)
        session_id = await repo.insert_session(
            conn,
            token_hash=hash_token(token),
            email=email,
            mfa_state=mfa_state,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=self._idle(now, absolute),
            abs_expires_at=absolute,
            ip=ip,
            ua_hash=hash_user_agent(user_agent),
        )
        await self._audit(
            conn,
            "session.created",
            email=email,
            session_id=session_id,
            ip=ip,
            ua=user_agent,
            request_id=request_id,
            detail={"mfa_state": mfa_state},
        )
        row = await repo.get_by_id(conn, session_id)
        return token, Session.from_row(row)

    # -- authentication --------------------------------------------------------
    async def authenticate(
        self,
        token: Optional[str],
        ip: Optional[str],
        user_agent: Optional[str],
        request_id: Optional[str] = None,
    ) -> AuthResult:
        """Resolve a cookie token to a live session bound to this client.

        A binding mismatch (different address bucket or user agent) revokes the
        session and audits it. ``last_seen`` moves at most once a minute."""
        if not token or len(token) > 256:
            return AuthResult(None, UNKNOWN)
        now = self._clock.now()
        async with self._engine.begin() as conn:
            row = await repo.get_by_token_hash(conn, hash_token(token))
            if row is None:
                return AuthResult(None, UNKNOWN)
            if row.revoked_at is not None:
                return AuthResult(None, REVOKED)
            if row.abs_expires_at <= now:
                return AuthResult(None, ABSOLUTE)
            if row.idle_expires_at <= now:
                return AuthResult(None, IDLE)
            bound_ip = str(row.ip) if row.ip is not None else None
            same_ip = rate_limit_key(bound_ip) == rate_limit_key(ip)
            same_ua = bytes(row.ua_hash or b"") == hash_user_agent(user_agent)
            if not (same_ip and same_ua):
                await self._revoke_rows(
                    conn,
                    [row.id],
                    "binding_mismatch",
                    "system",
                    ip=ip,
                    ua=user_agent,
                    request_id=request_id,
                    action="session.binding_mismatch",
                )
                return AuthResult(None, BINDING)
            session = Session.from_row(row)
            if (now - row.last_seen_at).total_seconds() >= TOUCH_INTERVAL_SECONDS:
                idle = self._idle(now, row.abs_expires_at)
                await repo.touch(conn, row.id, now, idle)
                session = Session.from_row(await repo.get_by_id(conn, row.id))
            return AuthResult(session, OK)

    # -- privilege changes -----------------------------------------------------
    async def promote_to_mfa(
        self,
        session: Session,
        token: str,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        *,
        conn: Optional[AsyncConnection] = None,
    ) -> Optional[str]:
        """Second factor passed: the session becomes ``mfa_ok`` under a NEW
        token (the old one stops working) and starts its step-up window.
        Returns the new token, or None when ``token`` no longer matches (a
        replay). Pass ``conn`` to join the caller's transaction."""
        if conn is None:
            async with self._engine.begin() as own:
                return await self.promote_to_mfa(
                    session, token, ip, user_agent, request_id, conn=own
                )
        now = self._clock.now()
        fresh = new_token()
        changed = await repo.promote(
            conn,
            session.id,
            hash_token(token),
            hash_token(fresh),
            now,
            self._idle(now, session.abs_expires_at),
        )
        if changed is None:
            return None
        await self._audit(
            conn,
            "session.rotated",
            email=session.email,
            session_id=session.id,
            ip=ip,
            ua=user_agent,
            request_id=request_id,
            detail={"mfa_state": "mfa_ok"},
        )
        return fresh

    def stepup_fresh(
        self, session: Session, max_age_seconds: int = STEPUP_MAX_AGE_SECONDS
    ) -> bool:
        """Whether the session's second factor was confirmed recently enough
        for a sensitive action (the 2FA stage sets ``stepup_at``)."""
        if session.mfa_state != "mfa_ok" or session.stepup_at is None:
            return False
        age = (self._clock.now() - session.stepup_at).total_seconds()
        return 0 <= age <= min(max_age_seconds, 600)

    # -- revocation ------------------------------------------------------------
    async def logout(
        self, session: Session, ip=None, user_agent=None, request_id=None
    ) -> None:
        async with self._engine.begin() as conn:
            await self._revoke_rows(
                conn,
                [session.id],
                "logout",
                session.email,
                ip=ip,
                ua=user_agent,
                request_id=request_id,
                actor_kind="admin",
                action="session.logout",
            )

    async def revoke_own(
        self, actor: Session, session_id: uuid.UUID, ip=None, user_agent=None,
        request_id=None,
    ) -> bool:
        """Revoke one of the actor's own sessions."""
        async with self._engine.begin() as conn:
            row = await repo.get_by_id(conn, session_id)
            if row is None or row.email != actor.email:
                return False
            return bool(
                await self._revoke_rows(
                    conn, [session_id], "revoked_by_owner", actor.email,
                    ip=ip, ua=user_agent, request_id=request_id, actor_kind="admin",
                )
            )

    async def revoke_other_admin(
        self, actor: Session, session_id: uuid.UUID, ip=None, user_agent=None,
        request_id=None,
    ) -> Optional[bool]:
        """Revoke another admin's session. None when the actor has no fresh
        step-up (the hook: the 2FA stage issues the step-up), else whether a
        session was revoked."""
        if not self.stepup_fresh(actor):
            return None
        async with self._engine.begin() as conn:
            row = await repo.get_by_id(conn, session_id)
            if row is None:
                return False
            return bool(
                await self._revoke_rows(
                    conn, [session_id], "revoked_by_admin", actor.email,
                    ip=ip, ua=user_agent, request_id=request_id, actor_kind="admin",
                )
            )

    async def revoke_all(
        self, email: str, *, keep: Optional[uuid.UUID] = None, by: str = "system",
        reason: str = "revoke_all", ip=None, user_agent=None, request_id=None,
        actor_kind: str = "admin",
    ) -> int:
        """Revoke every live session of ``email`` (except ``keep``)."""
        async with self._engine.begin() as conn:
            live = await repo.list_live(conn, email.strip().lower(), self._clock.now())
            return await self._revoke_rows(
                conn, [r.id for r in live if r.id != keep], reason, by,
                ip=ip, ua=user_agent, request_id=request_id, actor_kind=actor_kind,
            )

    async def revoke_for_removed_admin(
        self, session: Session, request_id: Optional[str] = None
    ) -> None:
        async with self._engine.begin() as conn:
            await self._revoke_rows(
                conn, [session.id], "admin_removed", "system", request_id=request_id
            )

    async def sweep_removed_admins(self, listed: Collection[str]) -> int:
        """Startup sweep: revoke live sessions whose email is no longer listed."""
        keep = {e.strip().lower() for e in listed}
        async with self._engine.begin() as conn:
            live = await repo.list_live_all(conn, self._clock.now())
            stale = [r.id for r in live if r.email.strip().lower() not in keep]
            return await self._revoke_rows(conn, stale, "admin_removed", "system")

    async def list_live(self, email: str) -> list[Session]:
        async with self._engine.connect() as conn:
            rows = await repo.list_live(conn, email.strip().lower(), self._clock.now())
        return [Session.from_row(r) for r in rows]

    # -- housekeeping ----------------------------------------------------------
    async def cleanup(self) -> dict:
        """Delete long-finished sessions and old challenges; safe to run often."""
        now = self._clock.now()
        async with self._engine.begin() as conn:
            sessions_gone = await repo.delete_finished(
                conn, now - timedelta(days=FINISHED_KEEP_DAYS)
            )
            challenges_gone = await repo.delete_old_challenges(
                conn, now - timedelta(days=1)
            )
        return {"sessions": sessions_gone, "challenges": challenges_gone}
