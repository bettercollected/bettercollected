"""The address a request came from, behind trusted proxies only.

X-Forwarded-For is a list the client starts and each proxy appends to, so
only the entries added by proxies we trust mean anything. Starting at the
direct peer, walk leftwards through trusted proxies (loopback and private
networks, plus ``API_TRUSTED_PROXIES``); the first other address is the hop
that reached our edge. When that hop is a Cloudflare edge (and Cloudflare is
trusted), the client is Cloudflare's ``CF-Connecting-IP``, which Cloudflare
sets itself and a client can't forge through it. The header is never read
for a request that didn't come through a Cloudflare hop.
"""

import ipaddress
from functools import lru_cache
from typing import Optional, Tuple, Union

from starlette.requests import Request

Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

# entries of X-Forwarded-For looked at, from the right; a longer chain is
# cut there (its leftmost entries are the client's to choose anyway)
MAX_FORWARDED_HOPS = 16

# always trusted: a proxy in front of the container connects from these
PRIVATE_NETWORKS = (
    "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7"
)

# Cloudflare's published edge ranges, https://www.cloudflare.com/ips-v4 and
# https://www.cloudflare.com/ips-v6, as of 2026-10-06. API_CLOUDFLARE_IPS
# replaces them when Cloudflare publishes new ones.
CLOUDFLARE_IPS = ",".join(
    (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)


@lru_cache(maxsize=16)
def parse_networks(spec: str) -> Tuple[Network, ...]:
    """``spec``: comma-separated addresses or CIDRs; invalid entries are ignored."""
    networks = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _address(value: str) -> Optional[Address]:
    value = (value or "").strip()
    if value.startswith("[") and "]" in value:  # [v6]:port
        value = value[1 : value.index("]")]
    elif value.count(":") == 1:  # v4:port
        value = value.split(":", 1)[0]
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped or address


def _within(address: Address, networks: Tuple[Network, ...]) -> bool:
    return any(address.version == n.version and address in n for n in networks)


def client_ip(
    request: Request,
    trusted_proxies: str = "",
    cloudflare_ips: Optional[str] = None,
) -> Optional[str]:
    """The client's address as a string, or None when it can't be told.

    ``trusted_proxies`` adds to the private networks; ``cloudflare_ips``
    (None: Cloudflare not trusted) are the edges whose CF-Connecting-IP is
    believed."""
    peer = _address(request.client.host) if request.client else None
    if peer is None:
        return None
    trusted = parse_networks(f"{PRIVATE_NETWORKS},{trusted_proxies or ''}")
    edge: Optional[Address] = None  # the first hop that isn't our proxy
    if not _within(peer, trusted):
        edge = peer
    else:
        hops = []
        for header in request.headers.getlist("x-forwarded-for"):
            hops.extend(header.split(","))
        for raw in reversed(hops[-MAX_FORWARDED_HOPS:]):
            address = _address(raw)
            if address is None:
                # garbage in the chain: nothing left of it can be believed
                break
            if not _within(address, trusted):
                edge = address
                break
            peer = address
    if edge is None:
        # every hop was a trusted proxy (or none was named): the leftmost
        # one we could read is as close to the client as we get
        return str(peer)
    if cloudflare_ips is not None and _within(edge, parse_networks(cloudflare_ips)):
        connecting = _address(request.headers.get("cf-connecting-ip", ""))
        if connecting is not None:
            return str(connecting)
    return str(edge)


def request_client_ip(request: Request) -> Optional[str]:
    """``client_ip`` with the API settings (TRUSTED_PROXIES, TRUST_CLOUDFLARE,
    CLOUDFLARE_IPS)."""
    from backend.config import settings

    api = settings.api_settings
    cloudflare = (api.CLOUDFLARE_IPS or CLOUDFLARE_IPS) if api.TRUST_CLOUDFLARE else None
    return client_ip(request, api.TRUSTED_PROXIES, cloudflare)
