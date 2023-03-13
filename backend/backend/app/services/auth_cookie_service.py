import calendar
import http.cookies
import uuid
from datetime import timedelta, datetime

import jwt
from starlette.responses import Response

from backend.config import settings
from common.models.user import User


# TODO move this to auth server
def set_token_to_response(
    user: User, expiry_after: timedelta, cookie_key: str, response: Response
):
    expiry = get_expiry_epoch_after(expiry_after)
    token = jwt.encode(
        {
            "id": user.id,
            "sub": user.sub,
            "roles": user.roles,
            "services": user.services,
            "exp": expiry,
            "jti": str(uuid.uuid4()),
        },
        settings.auth_settings.JWT_SECRET,
        algorithm="HS256",
    )
    set_token_cookie(response, cookie_key, token)


def set_access_token_to_response(user: User, response: Response):
    set_token_to_response(
        user,
        timedelta(minutes=settings.auth_settings.ACCESS_TOKEN_EXPIRY_IN_MINUTES),
        "Authorization",
        response,
    )


def set_refresh_token_to_response(user: User, response: Response):
    set_token_to_response(
        user,
        timedelta(days=settings.auth_settings.REFRESH_TOKEN_EXPIRY_IN_DAYS),
        "RefreshToken",
        response,
    )


def set_tokens_to_response(user: User, response: Response):
    set_access_token_to_response(user=user, response=response)
    set_refresh_token_to_response(user=user, response=response)


def get_expiry_epoch_after(time_delta: timedelta = timedelta()):
    return calendar.timegm((datetime.utcnow() + time_delta).utctimetuple())


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


def set_token_cookie(response: Response, key: str, token: str):
    should_be_secure = False if "localhost" in settings.api_settings.HOST else True
    same_site = "none" if should_be_secure else "lax"
    set_cookie(
        response=response,
        key=key,
        value=token,
        httponly=True,
        secure=should_be_secure,
        # TODO prevent against csrf with same site after fix
        samesite=same_site,
        max_age=settings.auth_settings.REFRESH_TOKEN_EXPIRY_IN_DAYS * 24 * 60 * 60,
    )


def delete_token_cookie(response: Response):
    should_be_secure = False if "localhost" in settings.auth_settings.HOST else True
    same_site = "none" if should_be_secure else "lax"
    delete_cookie(
        response=response,
        key="Authorization",
        httponly=True,
        secure=should_be_secure,
        # TODO prevent against csrf with same site after fix
        samesite=same_site,
    )
    delete_cookie(
        response=response,
        key="Refresh_token",
        httponly=True,
        secure=should_be_secure,
        # TODO prevent against csrf with same site after fix
        samesite=same_site,
    )
