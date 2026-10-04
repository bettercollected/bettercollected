import calendar
import http.cookies
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from common.models.user import User
from starlette.responses import Response

from backend.config import settings


ACCESS_TOKEN_COOKIE = "Authorization"
REFRESH_TOKEN_COOKIE = "RefreshToken"
# ``typ`` claim: an access token is never accepted as a refresh token and the
# other way round (both are httpOnly cookies signed with the same secret).
ACCESS = "access"
REFRESH = "refresh"


def new_jti() -> str:
    return str(uuid.uuid4())


def _encode(user: User, *, typ: str, exp: int, jti: str) -> str:
    claims = {
        "id": user.id,
        "sub": user.sub,
        "roles": user.roles,
        "plan": user.plan,
        # proven at sign-in; auth grants config-named platform admins only then
        "email_verified": user.email_verified is True,
        "exp": exp,
        "jti": jti,
        "typ": typ,
    }
    if user.sid:
        claims["sid"] = user.sid
    if user.auth_method:
        # "sso": the platform-admin grant ignores this session (docs/sso.md)
        claims["auth_method"] = user.auth_method
    if user.session_scope:
        # "respondent": no workspace permissions (authorization_service)
        claims["session_scope"] = user.session_scope
        claims["scope_workspace_id"] = user.scope_workspace_id
    return jwt.encode(claims, settings.auth_settings.JWT_SECRET, algorithm="HS256")


def access_token_for(user: User) -> str:
    expiry = timedelta(minutes=settings.auth_settings.ACCESS_TOKEN_EXPIRY_IN_MINUTES)
    return _encode(
        user, typ=ACCESS, exp=get_expiry_epoch_after(expiry), jti=new_jti()
    )


def set_access_token_to_response(user: User, response: Response) -> str:
    """A fresh access token for ``user``'s session (``user.sid``); returns it."""
    token = access_token_for(user)
    set_token_cookie(
        response,
        ACCESS_TOKEN_COOKIE,
        token,
        settings.auth_settings.ACCESS_TOKEN_EXPIRY_IN_MINUTES * 60,
    )
    return token


def set_refresh_token_to_response(
    user: User, response: Response, *, jti: str, expires_at: datetime
) -> str:
    """The session's refresh token: ``jti`` must be the one the session
    record holds as current, ``expires_at`` its expiry."""
    exp = calendar.timegm(expires_at.astimezone(timezone.utc).utctimetuple())
    token = _encode(user, typ=REFRESH, exp=exp, jti=jti)
    max_age = max(0, exp - get_expiry_epoch_after())
    set_token_cookie(response, REFRESH_TOKEN_COOKIE, token, max_age)
    return token


def get_expiry_epoch_after(time_delta: timedelta = timedelta()):
    return calendar.timegm((datetime.now(timezone.utc) + time_delta).utctimetuple())


def set_cookie(
    response: Response,
    key: str,
    value: str = "",
    max_age: int = None,
    expires: int = None,
    path: str = "/",
    domain: str = None,
    secure: bool = False,
    httponly: bool = False,
    samesite: str = "lax",
) -> None:
    cookie: http.cookies.BaseCookie = http.cookies.SimpleCookie()
    cookie[key] = value
    if max_age is not None:
        cookie[key]["max-age"] = max_age
    if expires is not None:
        cookie[key]["expires"] = expires
    if path is not None:
        cookie[key]["path"] = path
    if domain is not None:
        cookie[key]["domain"] = domain
    if secure:
        cookie[key]["secure"] = True
    if httponly:
        cookie[key]["httponly"] = True
    if samesite is not None:
        assert samesite.lower() in [
            "strict",
            "lax",
            "none",
        ], "samesite must be either 'strict', 'lax' or 'none'"
        cookie[key]["samesite"] = samesite
    cookie_val = cookie.output(header="").strip()
    response.raw_headers.append((b"set-cookie", cookie_val.encode("latin-1")))


def delete_cookie(
    response: Response,
    key: str,
    path: str = "/",
    domain: str = None,
    secure: bool = False,
    httponly: bool = False,
    samesite: str = "lax",
) -> None:
    response.set_cookie(
        key,
        max_age=0,
        expires=0,
        path=path,
        domain=domain,
        secure=secure,
        httponly=httponly,
        samesite=samesite,
    )


def set_token_cookie(response: Response, key: str, token: str, expiry: float):
    should_be_secure = False if "localhost" in settings.api_settings.HOST else True
    same_site = "none" if should_be_secure else "lax"
    domain = (
        "." + settings.api_settings.DOMAIN if settings.api_settings.DOMAIN else None
    )
    set_cookie(
        response=response,
        key=key,
        domain=domain,
        value=token,
        httponly=True,
        secure=should_be_secure,
        samesite=same_site,
        max_age=int(expiry),
    )


def delete_token_cookie(response: Response):
    should_be_secure = False if "localhost" in settings.api_settings.HOST else True
    same_site = "none" if should_be_secure else "lax"
    domain = (
        "." + settings.api_settings.DOMAIN if settings.api_settings.DOMAIN else None
    )
    delete_cookie(
        response=response,
        key=ACCESS_TOKEN_COOKIE,
        domain=domain,
        httponly=True,
        secure=should_be_secure,
        samesite=same_site,
    )
    delete_cookie(
        response=response,
        key=REFRESH_TOKEN_COOKIE,
        domain=domain,
        httponly=True,
        secure=should_be_secure,
        samesite=same_site,
    )
