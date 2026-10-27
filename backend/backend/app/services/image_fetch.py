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
import ssl
from dataclasses import dataclass
from typing import Collection, Optional, Tuple
from urllib.parse import urljoin

import httpcore

from backend.app.services import safe_http
from backend.app.services.safe_http import (  # noqa: F401 - re-exported
    PinnedBackend,
    is_public_address,
    resolve,
)

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


def _checked_url(url: str, allowed_hosts: Optional[Collection[str]]) -> Tuple[str, str]:
    """``(url, host)`` for a fetchable address, or raises ``invalid_url``."""
    try:
        url, host = safe_http.checked_https_url(url, max_length=MAX_URL_LENGTH)
    except safe_http.UrlRefused as refused:
        if refused.code == "not_https":
            raise FetchRefused(
                "invalid_url", "Only https:// image addresses can be used."
            )
        raise FetchRefused("invalid_url", "That is not an image address we can use.")
    if allowed_hosts is not None and host not in allowed_hosts:
        raise FetchRefused("not_allowed", "That image address is not allowed.")
    return url, host


async def _public_address(host: str) -> str:
    try:
        # ``resolve`` is looked up here, in this module, on every call
        return await safe_http.public_address(host, lambda h, p: resolve(h, p))
    except safe_http.AddressRefused as refused:
        if refused.code == "not_allowed":
            raise FetchRefused("not_allowed", "That image address is not allowed.")
        raise FetchRefused("unreachable", "We couldn't reach that address.")


def network_backend(host: str, address: str) -> httpcore.AsyncNetworkBackend:
    """The connection for one request. Tests replace this."""
    return PinnedBackend(host, address)


_ssl_context = safe_http.ssl_context
_header = safe_http.header_value


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
