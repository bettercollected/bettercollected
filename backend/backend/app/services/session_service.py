"""Server-side sessions behind the cookie tokens.

Every sign-in creates a session (``sessions``); the tokens issued for it carry
its id as ``sid``. Access tokens are short-lived and verified without a
database read. Refreshing (any request whose access token expired, or
``POST /auth/refresh``) requires the session to exist, be unrevoked and
unexpired, and the user to still exist in auth, so revoking a session ends it
within one access-token lifetime.

Refresh tokens rotate on ``POST /auth/refresh`` (new ``jti``, same ``sid``). The
implicit refresh inside ``get_logged_user`` does not rotate: server-side
rendering forwards the browser's cookies and drops the response's
``Set-Cookie``, so a rotation there would never reach the browser. A refresh
token whose ``jti`` is neither the session's current one nor the one it
replaced within the grace period is a replay of a stolen token: the session is
revoked.

Tokens without ``sid`` (issued before sessions existed) are refused, so those
users sign in once more.
"""

import datetime as dt
import logging
from http import HTTPStatus
from typing import List, Optional

import httpx
import jwt
from beanie import PydanticObjectId
from common.models.user import User
from starlette.requests import Request
from starlette.responses import Response

from backend.app.exceptions import HTTPException
from backend.app.schemas.session import SessionDocument
from backend.app.services.auth_cookie_service import (
    ACCESS,
    ACCESS_TOKEN_COOKIE,
    REFRESH,
    REFRESH_TOKEN_COOKIE,
    new_jti,
    set_access_token_to_response,
    set_refresh_token_to_response,
)
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings

log = logging.getLogger(__name__)

USER_AGENT_MAX = 256


class RevokeReason:
    LOGOUT = "logout"
    SIGNED_OUT_ELSEWHERE = "signed_out_by_user"
    LOGOUT_EVERYWHERE = "logout_everywhere"
    REFRESH_TOKEN_REUSE = "refresh_token_reuse"
    USER_NOT_FOUND = "user_not_found"
    ACCOUNT_DELETED = "account_deleted"


class SessionEnded(HTTPException):
    """401 for a session that cannot continue (revoked, expired, unknown,
    legacy token): the exception handler also clears the token cookies."""

    clear_session_cookies = True

    def __init__(self, content: str = "Your session has ended. Please sign in again."):
        super().__init__(HTTPStatus.UNAUTHORIZED, content)


class AuthServiceUnavailable(Exception):
    """The auth service refused or failed a session refresh."""

    def __init__(self, status_code: int):
        super().__init__(status_code)
        self.status_code = status_code


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def aware(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    """Mongo hands back naive UTC datetimes; Postgres aware ones."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=dt.timezone.utc)


def decode_token(token: Optional[str], *, verify_exp: bool = True) -> Optional[dict]:
    """The claims of a token this backend signed, or None."""
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            key=settings.auth_settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": verify_exp},
        )
    except jwt.PyJWTError:
        return None


def user_from_access_token(token: Optional[str]) -> Optional[User]:
    """The signed-in user, if ``token`` is a live access token of a session.
    No database read: a revoked session keeps working until this expires."""
    claims = decode_token(token)
    if not claims or claims.get("typ") != ACCESS or not claims.get("sid"):
        return None
    try:
        return User(**claims)
    except ValueError:
        return None


def auth_http_client():
    """The client the refresh asks auth's /status with (a seam for tests)."""
    return httpx.AsyncClient()


class SessionService:
    def __init__(self, session_repo):
        self.session_repo = session_repo

    # -- sign-in -----------------------------------------------------------
    async def start(
        self, user: User, response: Response, request: Optional[Request] = None
    ) -> User:
        """A new session for a user who just signed in; sets both cookies and
        returns the user as the tokens describe them (with ``sid``)."""
        now = utcnow()
        expires_at = now + dt.timedelta(
            days=settings.auth_settings.REFRESH_TOKEN_EXPIRY_IN_DAYS
        )
        user_agent = request.headers.get("user-agent") if request else None
        session = SessionDocument(
            id=PydanticObjectId(),
            user_id=user.id,
            refresh_jti=new_jti(),
            last_refreshed_at=now,
            expires_at=expires_at,
            email_verified=user.email_verified is True,
            user_agent=user_agent[:USER_AGENT_MAX] if user_agent else None,
            created_at=now,
            updated_at=now,
        )
        await self.session_repo.save(session)
        user = user.model_copy(
            update={"sid": str(session.id), "email_verified": session.email_verified}
        )
        set_access_token_to_response(user, response)
        set_refresh_token_to_response(
            user, response, jti=session.refresh_jti, expires_at=expires_at
        )
        return user

    # -- refresh -----------------------------------------------------------
    async def refresh(
        self, request: Request, response: Response, *, rotate: bool
    ) -> User:
        """Continue the session named by the refresh cookie: a new access
        token (and, with ``rotate``, a new refresh token). Raises
        :class:`SessionEnded` when the session cannot continue."""
        token = request.cookies.get(REFRESH_TOKEN_COOKIE)
        if not token:
            # not signed in: nothing to clear
            raise HTTPException(HTTPStatus.UNAUTHORIZED, "No user logged in.")
        claims = decode_token(token)
        if not claims:
            raise SessionEnded()
        sid, jti = claims.get("sid"), claims.get("jti")
        if claims.get("typ") != REFRESH or not sid or not jti:
            # issued before sessions existed: sign in again (once)
            raise SessionEnded()
        session = await self.session_repo.get(sid)
        now = utcnow()
        if (
            session is None
            or session.user_id != claims.get("id")
            or session.revoked_at is not None
            or aware(session.expires_at) <= now
        ):
            raise SessionEnded()

        current = jti == session.refresh_jti
        if not current and not self._in_grace(session, jti, now):
            log.warning(
                "Refresh token reuse on session %s of user %s: session revoked",
                sid,
                session.user_id,
            )
            await self.session_repo.revoke(sid, RevokeReason.REFRESH_TOKEN_REUSE, now)
            raise SessionEnded()

        user = await self._current_user(session)
        token = set_access_token_to_response(user, response)
        # forwarded by the plugin proxy instead of the expired cookie
        request.state.access_token = token

        if not rotate:
            await self.session_repo.touch(sid, now)
            return user

        refresh_jti, expires_at = session.refresh_jti, aware(session.expires_at)
        if current:
            expires_at = now + dt.timedelta(
                days=settings.auth_settings.REFRESH_TOKEN_EXPIRY_IN_DAYS
            )
            rotated = await self.session_repo.rotate(
                sid, jti, new_jti(), now, expires_at
            )
            if rotated is None:
                # a parallel request rotated (or revoked) it first
                rotated = await self.session_repo.get(sid)
                if rotated is None or rotated.revoked_at is not None:
                    raise SessionEnded()
            refresh_jti, expires_at = rotated.refresh_jti, aware(rotated.expires_at)
        set_refresh_token_to_response(
            user, response, jti=refresh_jti, expires_at=expires_at
        )
        return user

    @staticmethod
    def _in_grace(session: SessionDocument, jti: str, now: dt.datetime) -> bool:
        rotated_at = aware(session.rotated_at)
        return (
            jti == session.previous_refresh_jti
            and rotated_at is not None
            and (now - rotated_at).total_seconds()
            <= settings.auth_settings.REFRESH_REUSE_GRACE_SECONDS
        )

    async def _current_user(self, session: SessionDocument) -> User:
        """The user as auth knows them now (roles, plan); a user auth no
        longer has ends the session."""
        async with auth_http_client() as http_client:
            reply = await http_client.get(
                settings.auth_settings.BASE_URL + "/auth/status",
                # the session's own claim, recorded at sign-in
                params={
                    "user_id": session.user_id,
                    "email_verified": session.email_verified is True,
                },
                headers=auth_service_headers(),
                timeout=60,
            )
        if reply.status_code == HTTPStatus.NOT_FOUND:
            await self.session_repo.revoke(
                str(session.id), RevokeReason.USER_NOT_FOUND, utcnow()
            )
            raise SessionEnded()
        if reply.status_code != HTTPStatus.OK:
            # e.g. 403/503 when AUTH_INTERNAL_NOTIFY_KEY is missing or differs
            # between the services: not the user's fault
            raise AuthServiceUnavailable(reply.status_code)
        body = reply.json()
        return User(
            **{
                **body,
                "id": str(body.get("id") or session.user_id),
                "sub": body.get("email"),
                "email_verified": session.email_verified is True,
                "sid": str(session.id),
            }
        )

    # -- revocation --------------------------------------------------------
    async def end_current(self, request: Request, reason: str = RevokeReason.LOGOUT):
        """Revoke the session the request's cookies belong to (logout).
        Expired tokens still name their session; anything else is ignored."""
        for cookie in (REFRESH_TOKEN_COOKIE, ACCESS_TOKEN_COOKIE):
            claims = decode_token(request.cookies.get(cookie), verify_exp=False)
            if claims and claims.get("sid"):
                await self.revoke(claims["sid"], claims.get("id"), reason)
                return

    async def revoke(self, sid: str, user_id: Optional[str], reason: str) -> bool:
        """Revoke one of ``user_id``'s sessions; False when it is not theirs
        or already ended."""
        session = await self.session_repo.get(sid)
        if session is None or session.user_id != user_id:
            return False
        return bool(await self.session_repo.revoke(sid, reason, utcnow()))

    async def revoke_all_for_user(
        self, user_id: str, reason: str, except_sid: Optional[str] = None
    ) -> int:
        """Logout everywhere (but ``except_sid``); also used when the account
        is deleted. Takes effect at each session's next refresh."""
        return await self.session_repo.revoke_all_for_user(
            user_id, reason, utcnow(), except_session_id=except_sid
        )

    async def list_for_user(self, user_id: str) -> List[SessionDocument]:
        now = utcnow()
        return [
            s
            for s in await self.session_repo.list_active_by_user(user_id)
            if aware(s.expires_at) > now
        ]
