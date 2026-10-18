"""The address a request came from, behind trusted proxies only.

Pure functions, no framework or global state, shared by the backend and any
other service that needs the real client address (for example an IP
allowlist).

The TCP peer is the client unless it is a proxy we were told to trust
(``trusted_proxies``: comma-separated addresses or CIDRs, IPv4 and IPv6; the
default trusts nobody). Only then are the forwarding headers believed:
``X-Forwarded-For`` is a list the client starts and each proxy appends to, so
it is walked from the right, skipping trusted proxies; the first other
address is the hop that reached our edge (never the left-most entry, which
the client chooses). When that hop is a Cloudflare edge (``cloudflare_ips``),
the client is Cloudflare's ``CF-Connecting-IP``. Neither header is read for a
request whose peer is not a trusted proxy. Every address is parsed strictly;
anything unparseable is treated as untrustworthy and never raises.
"""

import ipaddress
from functools import lru_cache
from typing import Iterable, Optional, Tuple, Union

Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

# entries of X-Forwarded-For looked at, from the right; a longer chain is
# cut there (its leftmost entries are the client's to choose anyway)
MAX_FORWARDED_HOPS = 16
# longest header value or address token looked at
MAX_HEADER_LENGTH = 4096

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



@lru_cache(maxsize=32)
def parse_networks(spec: Optional[str]) -> Tuple[Network, ...]:
    """``spec``: comma-separated addresses or CIDRs; invalid entries are ignored
    (a typo narrows trust, it never widens it)."""
    networks = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part or "%" in part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def parse_address(value: Optional[str]) -> Optional[Address]:
    """A bare address, ``v4:port``, ``[v6]`` or ``[v6]:port``; None for
    anything else. IPv4-mapped IPv6 addresses become IPv4."""
    value = (value or "").strip()
    if not value or len(value) > 64 or "%" in value:
        return None
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return None
        rest = value[end + 1 :]
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return None
        value = value[1:end]
    elif value.count(":") == 1:  # v4:port
        value, _, port = value.partition(":")
        if not port.isdigit():
            return None
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped or address


def rate_limit_key(client: Optional[str]) -> str:
    """The key a client address is limited or counted under: an IPv4 address
    as is, an IPv6 address by its /64 (one subscriber's network, so rotating
    through its addresses does not multiply the limit); "unknown" otherwise."""
    address = parse_address(client)
    if address is None:
        return "unknown"
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _within(address: Address, networks: Tuple[Network, ...]) -> bool:
    return any(address.version == n.version and address in n for n in networks)


def resolve_client_ip(
    peer: Optional[str],
    forwarded_for: Iterable[str] = (),
    cf_connecting_ip: Optional[str] = None,
    trusted_proxies: Optional[str] = "",
    cloudflare_ips: Optional[str] = None,
) -> Optional[str]:
    """The client's address as a string, or None when the peer is unreadable.

    ``peer``: the TCP peer. ``forwarded_for``: every X-Forwarded-For header
    value, in order. ``trusted_proxies``: the proxies whose headers are
    believed (empty: none, the peer is the client). ``cloudflare_ips``:
    Cloudflare's edges (None: CF-Connecting-IP is never read)."""
    try:
        return _resolve(
            peer, forwarded_for, cf_connecting_ip, trusted_proxies, cloudflare_ips
        )
    except Exception:  # never into the request path; the peer is the safe answer
        address = parse_address(peer)
        return str(address) if address is not None else None


def _resolve(peer, forwarded_for, cf_connecting_ip, trusted_proxies, cloudflare_ips):
    hop = parse_address(peer)
    if hop is None:
        return None
    trusted = parse_networks(trusted_proxies)
    if not _within(hop, trusted):
        return str(hop)  # not a proxy of ours: its headers are its own words
    edge: Optional[Address] = None  # the first hop that isn't our proxy
    hops = []
    for header in forwarded_for:
        if header and len(header) <= MAX_HEADER_LENGTH:
            hops.extend(header.split(","))
    for raw in reversed(hops[-MAX_FORWARDED_HOPS:]):
        address = parse_address(raw)
        if address is None:
            # garbage in the chain: nothing left of it can be believed
            break
        if not _within(address, trusted):
            edge = address
            break
        hop = address
    cloudflare = parse_networks(cloudflare_ips) if cloudflare_ips is not None else ()
    if edge is None and _within(hop, cloudflare):
        edge = hop  # a Cloudflare edge we trust connecting to us directly
    if edge is None:
        # every readable hop was a trusted proxy: the last we could read is
        # as close to the client as we get
        return str(hop)
    if _within(edge, cloudflare):
        if cf_connecting_ip and len(cf_connecting_ip) <= MAX_HEADER_LENGTH:
            connecting = parse_address(cf_connecting_ip)
            if connecting is not None:
                return str(connecting)
    return str(edge)
