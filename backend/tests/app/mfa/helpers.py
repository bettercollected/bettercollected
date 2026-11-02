"""Builders shared by the second-factor tests. Everything here is synthetic."""

import datetime as dt
import time
from dataclasses import dataclass

from common.ids import RecordId
from common.models.user import User
from common.security import totp
from common.security.clock import FakeClock

from backend.app.container import container
from backend.app.schemas.session import SessionDocument
from backend.app.services.auth_cookie_service import access_token_for
from backend.app.services.mfa.service import MfaService
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.config import settings


def new_clock() -> FakeClock:
    """A clock the test moves, starting now (rows are stamped by the real clock)."""
    return FakeClock(time.time())



@dataclass
class Account:
    user: User
    session: SessionDocument

    @property
    def cookies(self) -> dict:
        token = access_token_for(self.user)
        return {"Authorization": token, "RefreshToken": token}


async def signed_in(email="mfa@example.org", age_minutes=0, now=None) -> Account:
    """A user with a live session ``age_minutes`` old (a session record exists:
    the second-factor routes read it)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    user_id = str(RecordId())
    created = now - dt.timedelta(minutes=age_minutes)
    session = await container.session_repo().save(
        SessionDocument(
            id=RecordId(),
            user_id=user_id,
            refresh_jti="j",
            expires_at=now + dt.timedelta(days=30),
            created_at=created,
            updated_at=created,
        )
    )
    user = User(id=user_id, sub=email, roles=["FORM_CREATOR"], sid=str(session.id))
    return Account(user=user, session=session)


def service(clock: FakeClock, notifier=None) -> MfaService:
    """The service with a clock the test moves (the rate limiter reads it too)."""
    limiter = FixedWindowRateLimiter(
        container.rate_limit_repo(), settings.auth_settings.JWT_SECRET, clock=clock.time
    )
    return MfaService(
        factor_repo=container.user_totp_repo(),
        session_repo=container.session_repo(),
        session_service=container.session_service(),
        rate_limiter=limiter,
        crypto=container.crypto(),
        audit_repo=container.workspace_audit_repo(),
        clock=clock,
        issuer="Test",
        notifier=notifier,
        workspace_policy=container.totp_requirement(),
    )


def secret_of(enrol) -> str:
    return "".join(enrol.secret.split())


def code_now(secret: str, clock: FakeClock, offset: int = 0) -> str:
    return totp.hotp(totp.decode_secret(secret), totp.step_for(clock.time()) + offset)


async def enrolled(svc: MfaService, clock: FakeClock, account: Account):
    """Set the factor up; returns (secret, recovery codes)."""
    enrol = await svc.begin_enrolment(account.user)
    secret = secret_of(enrol)
    codes = await svc.confirm_enrolment(
        account.user, enrol.factor_id, code_now(secret, clock)
    )
    return secret, codes.recovery_codes


async def member(workspace, email, role=None, **user_extra):
    """A member of ``workspace`` (default role: editor) and the user as a
    session of theirs would carry it."""
    from backend.app.models.enum.workspace_roles import WorkspaceRoles
    from backend.app.schemas.workspace_user import WorkspaceUserDocument

    user = User(id=str(RecordId()), sub=email, roles=["FORM_CREATOR"], **user_extra)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=[role or WorkspaceRoles.COLLABORATOR],
        )
    )
    return user


def cookies_of_user(user: User) -> dict:
    from tests.app.auth_helpers import access_token

    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def give_factor(user_id: str, locale=None) -> None:
    """A confirmed authenticator app for ``user_id`` (no session needed)."""
    from backend.app.schemas.user_totp import CONFIRMED, UserTotpFactorDocument
    from backend.app.services.mfa.sealing import seal_secret

    factor_id = RecordId()
    await container.user_totp_repo().upsert(
        UserTotpFactorDocument(
            id=factor_id,
            user_id=str(user_id),
            state=CONFIRMED,
            locale=locale,
            secret_sealed=seal_secret(container.crypto(), user_id, factor_id, "ABCDEFGHIJKLMNOP"),
        )
    )


async def require_totp(workspace, required=True) -> None:
    await container.workspace_repo().set_fields(workspace, {"require_totp": required})
