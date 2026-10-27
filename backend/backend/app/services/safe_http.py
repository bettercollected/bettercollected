"""The rules for reaching an address someone else chose, shared by everything
in the backend that fetches or posts to one (``image_fetch`` for pasted image
addresses, ``registration`` for a workspace's case-system service).

This module holds the pieces, not a client:

- :func:`is_public_address`: whether a connection to an address stays on the
  public internet (private, loopback, link-local including the cloud metadata
  address 169.254.169.254, multicast, reserved, unspecified, shared
  carrier-grade NAT, and the same inside IPv4-mapped, 6to4, NAT64 and Teredo
  IPv6 addresses);
- :func:`checked_https_url`: ``https`` only, the default port only, no user
  name or password, an ASCII (IDNA) host name, no fragment;
- :func:`resolve` and :func:`public_address`: resolve the name ourselves and
  refuse it when *any* answer is not public;
- :class:`PinnedBackend`: the connection goes to the address we checked, so a
  second DNS answer (rebinding) can't send it elsewhere; TLS still verifies the
  certificate against the host name.

Callers re-check the host at every connection (never only when an address is
saved) and decide for themselves about redirects, sizes and timeouts.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urlsplit

import certifi
import httpcore

MAX_URL_LENGTH = 2048
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


class UrlRefused(Exception):
    """``code``: ``invalid_url`` (not a usable address) or ``not_https``."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AddressRefused(Exception):
    """``code``: ``unreachable`` (does not resolve) or ``not_allowed`` (an
    answer is not a public address)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def is_public_address(address) -> bool:
    """Whether a connection to ``address`` stays on the public internet."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return is_public_address(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            return is_public_address(ip.sixtofour)
        if ip.teredo is not None:
            return False
        if ip in _NAT64:
            return is_public_address(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
        if ip.is_site_local:
            return False
    return bool(
        ip.is_global
        and not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    )


def checked_https_url(
    url: str,
    *,
    max_length: int = MAX_URL_LENGTH,
    allow_query: bool = True,
) -> Tuple[str, str]:
    """``(normalised url, host)`` for an address we may connect to, or raises
    :class:`UrlRefused`. The normalised address has no fragment and carries the
    host as we checked it."""
    invalid = UrlRefused("invalid_url")
    if not isinstance(url, str):
        raise invalid
    url = url.strip()
    if not url or len(url) > max_length or not url.isascii():
        raise invalid
    if any(ch.isspace() or ord(ch) < 0x20 or ch == "\\" for ch in url):
        raise invalid
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise invalid
    if parts.scheme.lower() != "https":
        raise UrlRefused("not_https")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise invalid
    if port not in (None, 443):
        raise invalid
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise invalid
    if parts.query and not allow_query:
        raise invalid
    path = parts.path or "/"
    netloc = f"[{host}]" if ":" in host else host
    url = f"https://{netloc}{path}" + (f"?{parts.query}" if parts.query else "")
    return url, host


async def resolve(host: str, port: int = 443) -> List[str]:
    """Every address ``host`` resolves to. Tests replace the caller's reference
    to this (``registration.client.resolve``, ``image_fetch.resolve``); there is
    no setting that does."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: List[str] = []
    for _family, _type, _proto, _name, sockaddr in infos:
        address = sockaddr[0]
        if address not in addresses:
            addresses.append(address)
    return addresses


async def public_address(
    host: str,
    resolver: Callable[[str, int], Awaitable[List[str]]] = resolve,
    port: int = 443,
) -> str:
    """The address to connect to for ``host``: the first one, after checking
    that every answer is public. Raises :class:`AddressRefused`."""
    try:
        addresses = await resolver(host, port)
    except (OSError, UnicodeError):
        raise AddressRefused("unreachable")
    if not addresses:
        raise AddressRefused("unreachable")
    # every answer must be public, not just the first: a name that also
    # points inward is refused outright
    if not all(is_public_address(a) for a in addresses):
        raise AddressRefused("not_allowed")
    return addresses[0]


class PinnedBackend(httpcore.AsyncNetworkBackend):
    """Connects to the address we checked, whatever the host name resolves
    to by now. TLS (SNI and certificate checks) still uses the host name."""

    def __init__(self, host: str, address: str, inner=None):
        self._host = host
        self._address = address
        self._inner = inner if inner is not None else httpcore.AnyIOBackend()

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        if host != self._host:
            raise httpcore.ConnectError("unexpected host")
        return await self._inner.connect_tcp(
            self._address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, *args, **kwargs):
        raise httpcore.ConnectError("not supported")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def ssl_context() -> ssl.SSLContext:
    """Verifies the server certificate against the public CA bundle."""
    return ssl.create_default_context(cafile=certifi.where())


def header_value(headers, name: bytes) -> Optional[str]:
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1").strip()
    return None
