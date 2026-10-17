"""Fetch an image from an address we were given, without becoming a way into
our own network (SSRF).

Used for the Unsplash route (fixed host, no redirects) and for copying in an
image address a person pasted in the editor. The rules:

- ``https`` only, the default port only, no user name or password in the
  address, an ASCII (IDNA) host name;
- we resolve the name ourselves and refuse it when any address it resolves to
  is not a public one (private, loopback, link-local including the cloud
  metadata address 169.254.169.254, multicast, reserved, unspecified, shared
  carrier-grade NAT, and the same inside IPv4-mapped, 6to4, NAT64 or Teredo
  IPv6 addresses);
- the connection goes to the address we checked (``PinnedBackend``), so a
  second DNS answer (rebinding) can't send it elsewhere; TLS still verifies
  the certificate against the host name;
- at most ``max_redirects`` redirects, each checked like the first address;
- connect/read timeouts and an overall deadline, at most ``max_bytes`` read
  while streaming, and only JPEG, PNG or WebP content types.

This module never decodes an image: the document sandbox does
(``services/image_service.py``).
"""

import asyncio
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from typing import Collection, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

import certifi
import httpcore

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_URL_LENGTH = 2048
# never AVIF, GIF or SVG: the sandbox re-encodes these three only
IMAGE_CONTENT_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
}
TIMEOUTS = {"connect": 5.0, "read": 10.0, "write": 10.0, "pool": 5.0}
TOTAL_TIMEOUT_S = 30.0
_REDIRECTS = {301, 302, 303, 307, 308}
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_USER_AGENT = b"bettercollected-image-fetch/1.0"


class FetchRefused(Exception):
    """The address or what it answered is refused. ``code`` is one of
    ``invalid_url``, ``not_allowed``, ``unreachable``, ``too_large``,
    ``not_image``, ``too_many_redirects``, ``timeout``."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FetchedImage:
    data: bytes
    content_type: str


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


def _checked_url(url: str, allowed_hosts: Optional[Collection[str]]) -> Tuple[str, str]:
    """``(url, host)`` for a fetchable address, or raises ``invalid_url``."""
    invalid = FetchRefused("invalid_url", "That is not an image address we can use.")
    if not isinstance(url, str):
        raise invalid
    url = url.strip()
    if not url or len(url) > MAX_URL_LENGTH or not url.isascii():
        raise invalid
    if any(ch.isspace() or ord(ch) < 0x20 or ch == "\\" for ch in url):
        raise invalid
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise invalid
    if parts.scheme.lower() != "https":
        raise FetchRefused("invalid_url", "Only https:// image addresses can be used.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise invalid
    if port not in (None, 443):
        raise invalid
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise invalid
    if allowed_hosts is not None and host not in allowed_hosts:
        raise FetchRefused("not_allowed", "That image address is not allowed.")
    # without the fragment, and with the host as we checked it
    path = parts.path or "/"
    netloc = f"[{host}]" if ":" in host else host
    url = f"https://{netloc}{path}" + (f"?{parts.query}" if parts.query else "")
    return url, host


async def resolve(host: str, port: int = 443) -> List[str]:
    """Every address ``host`` resolves to. Tests replace this."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: List[str] = []
    for _family, _type, _proto, _name, sockaddr in infos:
        address = sockaddr[0]
        if address not in addresses:
            addresses.append(address)
    return addresses


async def _public_address(host: str) -> str:
    try:
        addresses = await resolve(host, 443)
    except (OSError, UnicodeError):
        raise FetchRefused("unreachable", "We couldn't reach that address.")
    if not addresses:
        raise FetchRefused("unreachable", "We couldn't reach that address.")
    # every answer must be public, not just the first: a name that also
    # points inward is refused outright
    if not all(is_public_address(a) for a in addresses):
        raise FetchRefused("not_allowed", "That image address is not allowed.")
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


def network_backend(host: str, address: str) -> httpcore.AsyncNetworkBackend:
    """The connection for one request. Tests replace this."""
    return PinnedBackend(host, address)


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _header(headers, name: bytes) -> Optional[str]:
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1").strip()
    return None


async def _get_once(url: str, host: str, address: str, max_bytes: int):
    """``("redirect", location)`` or ``("image", FetchedImage)``."""
    request_headers = [
        (b"User-Agent", _USER_AGENT),
        (b"Accept", b"image/webp,image/png,image/jpeg"),
        (b"Accept-Encoding", b"identity"),
    ]
    async with httpcore.AsyncConnectionPool(
        ssl_context=_ssl_context(),
        network_backend=network_backend(host, address),
        max_connections=1,
        retries=0,
        http2=False,
    ) as pool:
        async with pool.stream(
            "GET", url, headers=request_headers, extensions={"timeout": TIMEOUTS}
        ) as response:
            if response.status in _REDIRECTS:
                location = _header(response.headers, b"location")
                if not location:
                    raise FetchRefused("unreachable", "We couldn't reach that image.")
                return "redirect", location
            if response.status != 200:
                raise FetchRefused("unreachable", "We couldn't reach that image.")
            declared = (_header(response.headers, b"content-type") or "").split(";")[0]
            content_type = IMAGE_CONTENT_TYPES.get(declared.strip().lower())
            if content_type is None:
                raise FetchRefused(
                    "not_image", "That address is not a JPEG, PNG or WebP image."
                )
            length = _header(response.headers, b"content-length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise FetchRefused("too_large", "That image is larger than 10 MB.")
            if (_header(response.headers, b"content-encoding") or "identity") not in (
                "identity",
                "",
            ):
                raise FetchRefused("not_image", "That image could not be read.")
            chunks, total = [], 0
            async for chunk in response.aiter_stream():
                total += len(chunk)
                if total > max_bytes:
                    raise FetchRefused("too_large", "That image is larger than 10 MB.")
                chunks.append(chunk)
            if not total:
                raise FetchRefused("not_image", "That image is empty.")
            return "image", FetchedImage(b"".join(chunks), content_type)


async def fetch_image(
    url: str,
    *,
    allowed_hosts: Optional[Collection[str]] = None,
    max_redirects: int = MAX_REDIRECTS,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> FetchedImage:
    """The image at ``url`` (raw bytes, not decoded), or raises FetchRefused."""

    async def run() -> FetchedImage:
        current = url
        for _hop in range(max_redirects + 1):
            current, host = _checked_url(current, allowed_hosts)
            address = await _public_address(host)
            try:
                kind, value = await _get_once(current, host, address, max_bytes)
            except httpcore.TimeoutException:
                raise FetchRefused("timeout", "That image took too long to load.")
            except (httpcore.NetworkError, httpcore.ProtocolError, ssl.SSLError):
                raise FetchRefused("unreachable", "We couldn't reach that image.")
            if kind == "image":
                return value
            current = urljoin(current, value)
        raise FetchRefused(
            "too_many_redirects", "That image address redirects too often."
        )

    try:
        return await asyncio.wait_for(run(), TOTAL_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise FetchRefused("timeout", "That image took too long to load.")
