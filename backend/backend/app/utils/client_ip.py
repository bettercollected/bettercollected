"""The address a request came from (see ``common.utils.client_ip``).

The default trusts no proxy: the TCP peer is the client. Set
``TRUSTED_PROXIES`` (alias ``API_TRUSTED_PROXIES``) to the proxies in front
of the API so their ``X-Forwarded-For`` / ``CF-Connecting-IP`` are believed.
"""

from typing import Optional

from starlette.requests import Request

from common.utils.client_ip import (  # noqa: F401  (re-exported)
    CLOUDFLARE_IPS,
    parse_address,
    parse_networks,
    rate_limit_key,
    resolve_client_ip,
)


def client_ip(
    request: Request,
    trusted_proxies: str = "",
    cloudflare_ips: Optional[str] = None,
) -> Optional[str]:
    """The client's address as a string, or None when it can't be told."""
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
