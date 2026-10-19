"""Security headers set on every response of the admin service, errors included."""

from typing import Iterable, List, Tuple

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

# ``same-origin``, not ``no-referrer``: with ``no-referrer`` a browser sends
# ``Origin: null`` on a same-origin form post, which the CSRF check (rightly)
# refuses, so no portal form could be submitted. Nothing is sent cross-origin.
SECURITY_HEADERS: Tuple[Tuple[bytes, bytes], ...] = (
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode("ascii")),
    (b"referrer-policy", b"same-origin"),
    (b"x-content-type-options", b"nosniff"),
    (b"cache-control", b"no-store"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b""),
)

# Fonts are the one thing a browser may keep: a handler sets exactly this value, and
# only it survives (every other response, a font error included, stays no-store).
FONT_CACHE_CONTROL = "public, max-age=31536000, immutable"

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
    headers = list(headers)
    keep_cache = any(
        k.lower() == b"cache-control" and v == FONT_CACHE_CONTROL.encode("ascii") for k, v in headers
    )
    kept = [(k, v) for k, v in headers if k.lower() not in _NAMES]
    ours = [h for h in SECURITY_HEADERS if not (keep_cache and h[0] == b"cache-control")]
    if keep_cache:
        kept.append((b"cache-control", FONT_CACHE_CONTROL.encode("ascii")))
    return kept + ours
