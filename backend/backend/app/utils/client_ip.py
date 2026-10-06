"""The address a request came from, behind trusted proxies only.

X-Forwarded-For is a list the client starts and each proxy appends to, so
only the entries added by proxies we trust mean anything: walk it from the
right, skipping trusted proxies, and the first other address is the client.
A request whose own peer is not a trusted proxy is identified by that peer,
whatever headers it sends.
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


@lru_cache(maxsize=8)
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


def _trusted(address: Address, networks: Tuple[Network, ...]) -> bool:
    return any(address.version == n.version and address in n for n in networks)


def client_ip(request: Request, trusted_proxies: str) -> Optional[str]:
    """The client's address as a string, or None when it can't be told."""
    peer = _address(request.client.host) if request.client else None
    if peer is None:
        return None
    networks = parse_networks(trusted_proxies)
    if not _trusted(peer, networks):
        return str(peer)
    hops = []
    for header in request.headers.getlist("x-forwarded-for"):
        hops.extend(header.split(","))
    for raw in reversed(hops[-MAX_FORWARDED_HOPS:]):
        address = _address(raw)
        if address is None:
            # garbage in the chain: nothing left of it can be believed
            break
        if not _trusted(address, networks):
            return str(address)
        peer = address
    # every hop was a trusted proxy (or none was named): the leftmost one
    # we could read is as close to the client as we get
    return str(peer)
