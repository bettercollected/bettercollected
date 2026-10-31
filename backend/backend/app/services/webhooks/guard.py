"""Whether an address may be a webhook's destination, checked when it is saved
(:func:`check_destination`) and again at every connection (the sender goes
through ``registration.client``, which resolves the host itself and connects to
the address it checked). The rules, shared with every other outgoing call of
the backend (``services/safe_http.py``):

- ``https`` only, port 443 only (a custom port would reach services that were
  never meant to be called from here), no user name or password, no fragment,
  no dot segments or encoded slashes in the path;
- an internationalised host name is converted to its ASCII (IDNA) form first, so
  what is checked, stored and connected to is one name; a host that does not
  convert is refused;
- no IP address as the host in any spelling (dotted, decimal, hex, octal, IPv6),
  no single-label host and no local-only suffix;
- the name must resolve, and *every* answer must be a public address: not
  private, loopback, link-local (the cloud metadata addresses 169.254.169.254
  and fd00:ec2::254 included), carrier-grade NAT, multicast, reserved or
  unspecified, nor any of those inside an IPv4-mapped, 6to4, NAT64 or Teredo
  IPv6 address.

Errors are our codes: ``invalid_url``, ``not_https``, ``not_allowed``,
``unreachable``.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
from typing import Tuple
from urllib.parse import urlsplit

from backend.app.services import safe_http
from backend.app.services.registration import client

RESOLVE_TIMEOUT_S = 10
_LOCAL_SUFFIXES = (
    ".local",
    ".localhost",
    ".localdomain",
    ".internal",
    ".intranet",
    ".lan",
    ".home",
    ".corp",
    ".private",
    ".home.arpa",
)
_TLD = re.compile(r"^(?:[a-z][a-z0-9-]*)$")
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class DestinationRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _ascii_host(host: str) -> str:
    """The IDNA (punycode) form of ``host``, lower case. Raises ``invalid_url``
    for a name that does not convert (a label too long, a forbidden character)."""
    try:
        return host.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        raise DestinationRefused("invalid_url")


def normalise(url: str) -> Tuple[str, str]:
    """``(address as stored, host)``: syntax only, no network."""
    invalid = DestinationRefused("invalid_url")
    if not isinstance(url, str):
        raise invalid
    url = url.strip()
    if not url or len(url) > safe_http.MAX_URL_LENGTH:
        raise invalid
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F or ch == "\\" for ch in url):
        raise invalid
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError for a bad port
    except ValueError:
        raise invalid
    if parts.scheme.lower() != "https":
        raise DestinationRefused("not_https")
    if "@" in parts.netloc:
        raise invalid
    raw_host = (parts.hostname or "").rstrip(".")
    if not raw_host or ":" in raw_host:
        raise invalid  # no host, or an IPv6 literal
    host = _ascii_host(raw_host)
    # only the host may be non-ASCII; the rest is already percent-encoded
    if not (parts.path + parts.query).isascii():
        raise invalid
    if parts.port not in (None, 443):
        raise invalid
    labels = host.split(".")
    if (
        len(labels) < 2
        or len(host) > 253
        or not all(_LABEL.match(label) for label in labels)
        or not _TLD.match(labels[-1])
        or ("." + host).endswith(_LOCAL_SUFFIXES)
    ):
        raise invalid
    try:
        ipaddress.ip_address(host)
        raise invalid
    except ValueError:
        pass
    rebuilt = f"https://{host}{parts.path or '/'}" + (
        f"?{parts.query}" if parts.query else ""
    )
    try:
        checked, checked_host = safe_http.checked_https_url(rebuilt)
    except safe_http.UrlRefused as refused:
        raise DestinationRefused(refused.code)
    if client.base_path_problem(checked.split("?", 1)[0]):
        raise invalid
    return checked, checked_host


async def check_destination(url: str, *, resolves: bool = True) -> Tuple[str, str]:
    """:func:`normalise`, then (``resolves``) the DNS check: every answer must
    be a public address. Returns ``(address, host)``."""
    checked, host = normalise(url)
    if not resolves:
        return checked, host
    try:
        await asyncio.wait_for(
            safe_http.public_address(host, lambda h, p: client.resolve(h, p)),
            RESOLVE_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise DestinationRefused("unreachable")
    except safe_http.AddressRefused as refused:
        raise DestinationRefused(refused.code)
    return checked, host
