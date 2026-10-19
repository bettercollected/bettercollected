"""Security headers set on every response of the admin service, errors included."""

from typing import Iterable, List, Tuple

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

# every powerful browser feature switched off: the portal needs none of them
PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), clipboard-read=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), hid=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), picture-in-picture=(), "
    "publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), "
    "web-share=(), xr-spatial-tracking=(), interest-cohort=()"
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
    (b"permissions-policy", PERMISSIONS_POLICY.encode("ascii")),
)
HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")

_NAMES = {name for name, _ in SECURITY_HEADERS} | {
    HSTS[0],
    b"server",
    b"access-control-allow-origin",
    b"access-control-allow-credentials",
}


def with_security_headers(
    headers: Iterable[Tuple[bytes, bytes]], https: bool = False
) -> List[Tuple[bytes, bytes]]:
    """``headers`` without any of ours (or a Server / CORS header a handler set),
    followed by ours. ``https`` adds HSTS (only meaningful, and only sent, when
    the request really arrived over TLS)."""
    kept = [(k, v) for k, v in headers if k.lower() not in _NAMES]
    extra = [HSTS] if https else []
    return kept + list(SECURITY_HEADERS) + extra
