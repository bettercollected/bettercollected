"""CSRF defences: per-session tokens, double-submit tokens, origin checks.

None of these functions raises on malformed input; they answer False.
"""

import base64
import hashlib
import hmac
import secrets
from typing import Collection, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from backend.admin.security.clock import Clock
from backend.admin.security.keycheck import require_key

FORM_TOKEN_MAX_AGE = 900  # a code is good for ten minutes; a form need not outlive it
_ALLOWED_FETCH_SITE = frozenset({"same-origin", "none"})


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _mac(key: bytes, label: str, value: str) -> str:
    key = require_key(key, "CSRF key")
    message = f"{label}|{value}".encode("utf-8")
    return _b64(hmac.new(key, message, hashlib.sha256).digest())


def session_token(csrf_key: bytes, session_id: str) -> str:
    """The CSRF token of a session: ``HMAC(csrf_key, session_id)``."""
    return _mac(csrf_key, "session", session_id)


def verify_session_token(
    csrf_key: bytes, session_id: str, token: Optional[str]
) -> bool:
    require_key(csrf_key, "CSRF key")
    if not isinstance(token, str) or not token:
        return False
    expected = session_token(csrf_key, session_id)
    return hmac.compare_digest(
        expected.encode("utf-8"), token.encode("utf-8", "replace")
    )


def issue_form_token(csrf_key: bytes, clock: Clock) -> str:
    """A double-submit token for a form shown before sign-in: set it as a
    cookie and as a hidden field; ``verify_form_token`` compares the two.

    The cookie must be a ``__Host-`` cookie (Secure, Path=/, no Domain) so a
    sibling subdomain cannot plant a token of its own, and the check must
    always be paired with ``origin_allowed``: a double-submit token alone
    does not stop a request that carries its own matching pair."""
    issued = str(int(clock.time()))
    nonce = _b64(secrets.token_bytes(16))
    return f"{issued}.{nonce}.{_mac(csrf_key, 'form', f'{issued}.{nonce}')}"


def verify_form_token(
    csrf_key: bytes,
    cookie_value: Optional[str],
    form_value: Optional[str],
    clock: Clock,
    max_age: int = FORM_TOKEN_MAX_AGE,
) -> bool:
    """Cookie and form field are equal, signed by us, and not older than
    ``max_age`` seconds."""
    require_key(csrf_key, "CSRF key")
    if not isinstance(cookie_value, str) or not isinstance(form_value, str):
        return False
    if not cookie_value or not hmac.compare_digest(
        cookie_value.encode("utf-8", "replace"), form_value.encode("utf-8", "replace")
    ):
        return False
    parts = cookie_value.split(".")
    if len(parts) != 3 or not parts[0].isascii() or not parts[0].isdigit():
        return False
    issued, nonce, signature = parts
    expected = _mac(csrf_key, "form", f"{issued}.{nonce}")
    if not hmac.compare_digest(
        expected.encode("utf-8"), signature.encode("utf-8", "replace")
    ):
        return False
    age = clock.time() - int(issued)
    return -60 <= age <= max_age


_DEFAULT_PORTS = {"http": 80, "https": 443}
Origin = Tuple[str, str, int]


def _origin_of(url: str) -> Optional[Origin]:
    """``(scheme, host, port)`` of an http(s) URL without credentials, the
    default port filled in; None for anything else."""
    try:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower()
        if scheme not in _DEFAULT_PORTS or not parts.hostname:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        port = parts.port
    except ValueError:
        return None
    return (
        scheme,
        parts.hostname.lower(),
        port if port is not None else _DEFAULT_PORTS[scheme],
    )


def _lower(headers: Mapping[str, str]) -> Mapping[str, str]:
    out = {}
    for key, value in headers.items():
        if isinstance(key, bytes):
            key = key.decode("latin-1")
        if isinstance(value, bytes):
            value = value.decode("latin-1")
        if isinstance(key, str) and isinstance(value, str):
            out[key.lower()] = value
    return out


def origin_allowed(
    headers: Mapping[str, str], allowed_origins: Collection[str]
) -> bool:
    """Whether a state-changing request comes from one of our own pages.

    ``allowed_origins`` are full origins (``https://admin.example.org``,
    ``http://localhost:8100``). ``Origin`` (``Referer`` when it is absent)
    must equal one of them in scheme, host and port (the scheme's default
    port is implied), so ``http://`` never passes for an ``https://`` portal.
    ``Sec-Fetch-Site``, when sent, must be ``same-origin`` or ``none``. With
    neither ``Origin`` nor ``Referer`` the answer is False. The Host
    allow-list is the gate's business, not this function's."""
    try:
        h = _lower(headers)
        fetch_site = h.get("sec-fetch-site")
        if (
            fetch_site is not None
            and fetch_site.strip().lower() not in _ALLOWED_FETCH_SITE
        ):
            return False
        source = h.get("origin")
        if source is None:
            source = h.get("referer")
        if source is None:
            return False
        origin = _origin_of(source)
        if origin is None:
            return False
        allowed = {o for o in (_origin_of(str(a)) for a in allowed_origins) if o}
        return origin in allowed
    except Exception:  # never raise on garbage
        return False
