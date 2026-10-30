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
_warned_unlisted_private_proxy = False


def _warn_if_proxy_unconfigured(request: Request, trusted_proxies: str) -> None:
    """Once per process each, say so when forwarding headers arrive from a
    private peer that is not trusted: while no proxy is trusted at all (the
    usual unconfigured reverse proxy), or while TRUSTED_PROXIES is set but
    leaves that peer out (a stale entry, e.g. a recreated proxy container with
    a new address, or a host name, which is not accepted). Logs no header value
    and no address; behaviour is unchanged."""
    global _warned_untrusted_private_peer, _warned_unlisted_private_proxy
    configured = bool((trusted_proxies or "").strip())
    if _warned_unlisted_private_proxy if configured else _warned_untrusted_private_peer:
        return
    headers = request.headers
    if "x-forwarded-for" not in headers and "cf-connecting-ip" not in headers:
        return
    peer = parse_address(request.client.host if request.client else None)
    if peer is None or not (peer.is_private or peer.is_loopback):
        return
    if not configured:
        _warned_untrusted_private_peer = True
        logger.warning(
            "Requests arrive from a private address with X-Forwarded-For set but "
            "TRUSTED_PROXIES is empty; every client behind your proxy shares one "
            "rate-limit bucket. Set TRUSTED_PROXIES to your proxy's address."
        )
        return
    if any(
        peer.version == network.version and peer in network
        for network in parse_networks(trusted_proxies)
    ):
        return
    _warned_unlisted_private_proxy = True
    logger.warning(
        "A proxy at a private address is not in TRUSTED_PROXIES (it sends "
        "X-Forwarded-For); all clients may share one address for rate limits. "
        "Add the proxy's address, or better the CIDR of the network between "
        "the proxy and the backend (TRUSTED_PROXIES takes addresses and CIDRs, "
        "not host names)."
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
