"""The address a request came from (see ``common.utils.client_ip``).

The default trusts no proxy: the TCP peer is the client. Set
``TRUSTED_PROXIES`` (alias ``API_TRUSTED_PROXIES``) to the proxies in front
of the API so their ``X-Forwarded-For`` / ``CF-Connecting-IP`` are believed.
"""

import logging
from typing import Optional

from starlette.requests import Request

from common.utils.client_ip import (  # noqa: F401  (re-exported)
    CLOUDFLARE_IPS,
    parse_address,
    parse_networks,
    rate_limit_key,
    resolve_client_ip,
)


logger = logging.getLogger(__name__)
_warned_untrusted_private_peer = False


def _warn_if_proxy_unconfigured(request: Request, trusted_proxies: str) -> None:
    """Once per process, say so when forwarding headers arrive from a private
    peer while no proxy is trusted (the usual unconfigured reverse proxy).
    Logs no header value and no address; behaviour is unchanged."""
    global _warned_untrusted_private_peer
    if _warned_untrusted_private_peer or (trusted_proxies or "").strip():
        return
    headers = request.headers
    if "x-forwarded-for" not in headers and "cf-connecting-ip" not in headers:
        return
    peer = parse_address(request.client.host if request.client else None)
    if peer is None or not (peer.is_private or peer.is_loopback):
        return
    _warned_untrusted_private_peer = True
    logger.warning(
        "Requests arrive from a private address with X-Forwarded-For set but "
        "TRUSTED_PROXIES is empty; every client behind your proxy shares one "
        "rate-limit bucket. Set TRUSTED_PROXIES to your proxy's address."
    )


def client_ip(
    request: Request,
    trusted_proxies: str = "",
    cloudflare_ips: Optional[str] = None,
) -> Optional[str]:
    """The client's address as a string, or None when it can't be told."""
    _warn_if_proxy_unconfigured(request, trusted_proxies)
    return resolve_client_ip(
        request.client.host if request.client else None,
        request.headers.getlist("x-forwarded-for"),
        request.headers.get("cf-connecting-ip"),
        trusted_proxies,
        cloudflare_ips,
    )


def request_client_ip(request: Request) -> Optional[str]:
    """``client_ip`` with the API settings (TRUSTED_PROXIES, TRUST_CLOUDFLARE,
    CLOUDFLARE_IPS)."""
    from backend.config import settings

    api = settings.api_settings
    cloudflare = (api.CLOUDFLARE_IPS or CLOUDFLARE_IPS) if api.TRUST_CLOUDFLARE else None
    return client_ip(request, api.TRUSTED_PROXIES, cloudflare)
