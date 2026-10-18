"""Security headers set on every response of the admin service, errors included."""

from typing import Iterable, List, Tuple

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

SECURITY_HEADERS: Tuple[Tuple[bytes, bytes], ...] = (
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode("ascii")),
    (b"referrer-policy", b"no-referrer"),
    (b"x-content-type-options", b"nosniff"),
    (b"cache-control", b"no-store"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b""),
)

_NAMES = {name for name, _ in SECURITY_HEADERS} | {
    b"server",
    b"access-control-allow-origin",
    b"access-control-allow-credentials",
}


def with_security_headers(
    headers: Iterable[Tuple[bytes, bytes]],
) -> List[Tuple[bytes, bytes]]:
    """``headers`` without any of ours (or a Server / CORS header a handler set),
    followed by ours."""
    kept = [(k, v) for k, v in headers if k.lower() not in _NAMES]
    return kept + list(SECURITY_HEADERS)
