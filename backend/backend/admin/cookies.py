"""Cookie names, attributes and parsing for the admin portal.

All cookies use the ``__Host-`` prefix: ``Secure``, ``Path=/``, no ``Domain``.
Browsers treat ``localhost`` as a secure context, so the portal works there
over plain HTTP; anywhere else it needs TLS.
"""

from http.cookies import CookieError, SimpleCookie
from typing import Optional

from starlette.responses import Response

SESSION_COOKIE = "__Host-bcadmin"
CHALLENGE_COOKIE = "__Host-bcadmin-ch"
FORM_COOKIE = "__Host-bcadmin-csrf"


def read_cookie(scope, name: str) -> Optional[str]:
    """The value of cookie ``name`` from the request headers (first match)."""
    for key, value in scope.get("headers", ()):
        if key != b"cookie":
            continue
        try:
            jar = SimpleCookie()
            jar.load(value.decode("latin-1"))
        except CookieError:
            continue
        morsel = jar.get(name)
        if morsel is not None:
            return morsel.value
    return None


def set_cookie(
    response: Response, name: str, value: str, max_age: Optional[int] = None
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )  # no domain, on purpose


def clear_cookie(response: Response, name: str) -> None:
    response.set_cookie(
        name, "", max_age=0, path="/", secure=True, httponly=True, samesite="strict"
    )
