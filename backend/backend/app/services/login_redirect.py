"""Where a sign-in may send the browser afterwards.

The page a sign-in started from (``client_referer_url``: the request's Referer,
carried through the provider's state) becomes the redirect after login. It is
only followed when it is on one of this instance's own origins: the client
URL (``API_CLIENT_URL``) and the ``allowed_origins`` the API already trusts for
CORS (the admin/client hosts seeded at install, plus each workspace's custom
domain, added when it is configured — respondents sign in from those). Anything
else goes to the default page, so a crafted sign-in link cannot bounce a
freshly signed-in user to another site.
"""

from typing import Iterable, Optional
from urllib.parse import urlsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


def origin_of(url: Optional[str]) -> Optional[str]:
    """``scheme://host[:port]`` of an absolute http(s) URL, lower-cased with
    the default port dropped; None for anything else (relative or
    scheme-relative URLs, credentials in the URL, backslashes, whitespace)."""
    if not isinstance(url, str) or not url:
        return None
    if any(c in url for c in "\\\t\r\n ") or any(ord(c) < 0x20 for c in url):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        return None
    origin = f"{scheme}://{parts.hostname.lower()}"
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        origin += f":{port}"
    return origin


def is_allowed_redirect(url: Optional[str], allowed_origins: Iterable[str]) -> bool:
    origin = origin_of(url)
    if origin is None:
        return False
    return origin in {o for o in (origin_of(a) for a in allowed_origins) if o}


def safe_redirect(
    url: Optional[str], allowed_origins: Iterable[str], default: str
) -> str:
    """``url`` when it is on an allowed origin, else ``default``."""
    return url if is_allowed_redirect(url, allowed_origins) else default
