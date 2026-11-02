"""The second-factor step of a sign-in (docs/totp.md).

An email-code or Google sign-in whose first factor passed, for an account that
has an authenticator app and while ``TOTP_ENABLED`` is on, does not create a
session yet. It sets a challenge cookie (a signed, short-lived token that names
the account, how it signed in and nothing else, and carries no permission) and
answers that a second factor is needed. ``complete`` takes the code, checks it
with every rule of :meth:`MfaService.check_code` and only then creates the
session, with ``mfa`` recorded. Until then there is no session row to refresh,
list or use, and the challenge opens no other route.

Single sign-on is never challenged (the identity provider's own policy), nor is
a respondent-scoped session (it holds no workspace permission).
"""

import datetime as dt
import logging
from http import HTTPStatus
from typing import Optional

import jwt
from common.models.user import User
from common.services.jwt_service import decode_with_ring, signing_secret
from starlette.requests import Request
from starlette.responses import Response

from backend.app.services.auth_cookie_service import (
    delete_cookie,
    new_jti,
    set_token_cookie,
)
from backend.app.services.mfa.service import (
    MfaService,
    _refused,
    refuse_when_off,
    totp_enabled,
)
from backend.app.services.session_service import RESPONDENT_SCOPE, SSO_METHOD
from backend.config import settings

log = logging.getLogger(__name__)

CHALLENGE_COOKIE = "McChallenge"
CHALLENGE_TYP = "mfa_challenge"
CHALLENGE_LIFETIME = dt.timedelta(minutes=5)
CLAIM_SCOPE = "mfa_challenge"


class SignedIn:
    """What a completed challenge gives back."""

    def __init__(self, user: User, method: str, recovery_left: Optional[int]):
        self.user = user
        self.method = method
        self.recovery_left = recovery_left


def _cookie_domain() -> Optional[str]:
    domain = settings.api_settings.DOMAIN
    return "." + domain if domain else None


def clear_challenge_cookie(response: Response) -> None:
    secure = "localhost" not in settings.api_settings.HOST
    delete_cookie(
        response,
        CHALLENGE_COOKIE,
        domain=_cookie_domain(),
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
    )


class MfaSignIn:
    def __init__(self, mfa_service: MfaService, session_service, factor_repo, rate_limiter):
        self._mfa = mfa_service
        self._sessions = session_service
        self._factors = factor_repo
        self._limiter = rate_limiter

    async def required_for(self, user: User, method: Optional[str] = None) -> bool:
        """Whether this first factor must be followed by a second one."""
        if not totp_enabled():
            return False
        if user.session_scope == RESPONDENT_SCOPE or method == SSO_METHOD:
            return False
        return await self._factors.confirmed(user.id) is not None

    def begin(self, user: User, method: str, response: Response) -> None:
        """Set the challenge cookie for ``user``, who passed the first factor."""
        now = dt.datetime.now(dt.timezone.utc)
        claims = {
            "typ": CHALLENGE_TYP,
            "jti": new_jti(),
            "exp": int((now + CHALLENGE_LIFETIME).timestamp()),
            "id": user.id,
            "sub": user.sub,
            "roles": user.roles,
            "plan": user.plan,
            "email_verified": user.email_verified is True,
            "method": method,
        }
        token = jwt.encode(
            claims, signing_secret(settings.auth_settings.JWT_SECRET), algorithm="HS256"
        )
        set_token_cookie(
            response, CHALLENGE_COOKIE, token, CHALLENGE_LIFETIME.total_seconds()
        )

    @staticmethod
    def _claims(request: Request) -> dict:
        token = request.cookies.get(CHALLENGE_COOKIE)
        try:
            claims = decode_with_ring(
                token or "",
                settings.auth_settings.JWT_SECRET,
                algorithms=["HS256"],
            )
        except jwt.PyJWTError:
            claims = None
        if (
            not claims
            or claims.get("typ") != CHALLENGE_TYP
            or not claims.get("id")
            or not claims.get("jti")
        ):
            raise _refused(
                HTTPStatus.UNAUTHORIZED,
                "mfa_challenge_expired",
                "Sign in again.",
            )
        return claims

    async def complete(
        self,
        request: Request,
        response: Response,
        code: Optional[str],
        client: Optional[str] = None,
    ) -> SignedIn:
        """The session, if ``code`` is right; the challenge is spent by it."""
        refuse_when_off()
        claims = self._claims(request)
        verified = await self._mfa._check(str(claims["id"]), code, client, None)
        expires = dt.datetime.fromtimestamp(claims["exp"], dt.timezone.utc)
        if not await self._limiter.claim(CLAIM_SCOPE, str(claims["jti"]), expires):
            # a second code arrived for a challenge that already made a session
            raise _refused(
                HTTPStatus.UNAUTHORIZED, "mfa_challenge_expired", "Sign in again."
            )
        user = User(
            id=str(claims["id"]),
            sub=claims["sub"],
            roles=claims.get("roles") or [],
            plan=claims.get("plan"),
            email_verified=claims.get("email_verified") is True,
        )
        user = await self._sessions.start(
            user,
            response,
            request,
            method=claims.get("method"),
            mfa_method=verified.method,
        )
        clear_challenge_cookie(response)
        return SignedIn(user, verified.method, verified.recovery_left)
