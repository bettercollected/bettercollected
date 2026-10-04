"""Which URLs an admin may hand to Polis to fetch (SSRF guard).

Polis fetches a SAML metadata URL when a connection is created, and an OIDC
discovery URL at sign-in time, from inside our network. So a URL is only
accepted when it is ``https``, carries no credentials, and its host is a
public address: an IP literal or every address its name resolves to must be
globally routable (no private, loopback, link-local, carrier-grade NAT,
multicast, reserved or unspecified ranges, IPv4 or IPv6).

The check runs before the URL is handed over; Polis resolves the name again
when it fetches, so a name that changes its answer in between (DNS
rebinding) is not covered here. Polis itself refuses private IP literals
again, and the deployment keeps Polis off the internal admin networks
(docs/sso.md).
"""

import asyncio
import ipaddress
import socket
from typing import Awaitable, Callable, Iterable, List, Optional
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048

# host -> its addresses; a seam so tests never resolve real names
Resolver = Callable[[str], Awaitable[List[str]]]


class UnsafeUrl(ValueError):
    """``code`` is stable for clients: invalid_url, https_required,
    unresolvable_host, private_address."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def system_resolver(host: str) -> List[str]:
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(host, None, type=socket.SOCK_STREAM), timeout=5
    )
    return [info[4][0] for info in infos]


def is_public_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(
        ip.is_global
        and not ip.is_private
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_unspecified
    )


def _ip_literal(host: str) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        return None


def parse_https_url(url: str) -> str:
    """The host of an absolute ``https`` URL without credentials, or
    UnsafeUrl. Does not resolve anything."""
    if (
        not isinstance(url, str)
        or not url
        or len(url) > MAX_URL_LENGTH
        or any(ch.isspace() or ord(ch) < 0x20 for ch in url)
        or "\\" in url
    ):
        raise UnsafeUrl("invalid_url", "Enter a valid URL.")
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 — raises on a bad port
    except ValueError:
        raise UnsafeUrl("invalid_url", "Enter a valid URL.")
    if parts.scheme.lower() != "https":
        raise UnsafeUrl("https_required", "The URL must start with https://.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UnsafeUrl("invalid_url", "The URL must not contain credentials.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeUrl("invalid_url", "Enter a valid URL.")
    return host


async def check_public_https_url(url: str, resolver: Optional[Resolver] = None) -> str:
    """``url`` when Polis may fetch it, else UnsafeUrl (see the module)."""
    host = parse_https_url(url)
    literal = _ip_literal(host)
    if literal is not None:
        addresses: Iterable[str] = [literal]
    else:
        if host == "localhost" or host.endswith(".localhost"):
            raise UnsafeUrl(
                "private_address", "The URL must point to a public internet address."
            )
        try:
            addresses = await (resolver or system_resolver)(host)
        except (OSError, asyncio.TimeoutError, UnicodeError):
            addresses = []
        if not addresses:
            raise UnsafeUrl(
                "unresolvable_host", "The URL's host name does not resolve."
            )
    if not all(is_public_address(a) for a in addresses):
        raise UnsafeUrl(
            "private_address", "The URL must point to a public internet address."
        )
    return url
