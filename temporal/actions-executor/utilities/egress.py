"""Where the executor may send a run's data: every outgoing call an action makes
(a webhook, Slack, Discord, an SMTP server) goes through this module.

Action parameters (a webhook address, an SMTP host) are set by form creators.
A stored address is only as trustworthy as whoever stored it, and from here a
connection reaches the stack's own services (the backend's internal listener,
Postgres, Redis, the Docker or Swarm API, a cloud metadata address), so the
rules are the backend's own for any address someone else chose
(``backend/app/services/safe_http.py``, written out here because the executor
is a separate package):

- ``https`` only, port 443 only, no user name or password, no fragment, no IP
  address as the host in any spelling, an IDNA (ASCII) host name;
- the host is resolved at **every** connection and *every* answer must be a
  public address (not private, loopback, link-local, carrier-grade NAT,
  multicast, reserved, unspecified, nor any of those inside an IPv4-mapped,
  6to4, NAT64 or Teredo IPv6 address); the connection goes to the address that
  was checked, so a name that rebinds between the lookup and the connection
  reaches nothing else; TLS still verifies the certificate against the host name;
- **no redirects**, a capped reply, bounded time, no proxy settings, no cookies.

Two exceptions, both set by the operator, never by a creator:

- ``ACTION_EGRESS_ALLOW`` (``host`` or ``host:port``, comma separated): hosts
  that may be internal and may use http or another port, because the operator
  deliberately sends actions there;
- the *trusted* hosts of a run: addresses in the action's own parameters, the
  defaults the instance's administrators set when they created the action (a
  workspace or a form overrides a value, it never makes its own value trusted).

Errors carry a code (``invalid_url``, ``not_https``, ``not_allowed``,
``unreachable``, ``timeout``, ``too_large``, ``redirect_refused``) and never the
address or the destination's reply.
"""

import ipaddress
import json
import re
import socket
import ssl
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode, urlsplit

import httpcore
import httpx

MAX_URL_LENGTH = 2048
MAX_BODY_BYTES = 1024 * 1024
MAX_REPLY_BYTES = 64 * 1024
TIMEOUTS = {"connect": 5.0, "read": 10.0, "write": 10.0, "pool": 5.0}
SMTP_PORTS = (25, 465, 587, 2525)
USER_AGENT = "bettercollected-actions/1"
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,100}$")
_FORBIDDEN_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}


class EgressRefused(Exception):
    """``code``: ``invalid_url``, ``not_https``, ``not_allowed``, ``unreachable``,
    ``timeout``, ``too_large`` or ``redirect_refused``. Never holds an address."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Reply:
    status_code: int
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")


def is_public_address(address: Any) -> bool:
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


def parse_allow(text: Optional[str]) -> List[Tuple[str, Optional[int]]]:
    """``ACTION_EGRESS_ALLOW``: ``host`` or ``host:port`` entries."""
    entries: List[Tuple[str, Optional[int]]] = []
    for raw in (text or "").split(","):
        raw = raw.strip().lower()
        if not raw:
            continue
        host, separator, port = raw.rpartition(":")
        if separator and port.isdigit() and ":" not in host:
            entries.append((host, int(port)))
        else:
            entries.append((raw, None))
    return entries


def _ascii_host(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii").lower().rstrip(".")
    except (UnicodeError, ValueError):
        raise EgressRefused("invalid_url") from None


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _valid_name(host: str) -> bool:
    """A host name, not a number in disguise: the last label has a letter and is
    not hexadecimal (``2130706433``, ``0x7f.1``, ``0177.0.0.1`` are addresses)."""
    if not host or len(host) > 253:
        return False
    labels = host.split(".")
    if not all(_HOST_LABEL.match(label) for label in labels):
        return False
    last = labels[-1]
    return any(ch.isalpha() for ch in last) and not re.fullmatch(r"0x[0-9a-f]*", last)


def _allowed(host: str, port: int, allow: Sequence[Tuple[str, Optional[int]]]) -> bool:
    for entry_host, entry_port in allow:
        if entry_host == host and (
            port == entry_port if entry_port is not None else port in (80, 443)
        ):
            return True
    return False


def trusted_hosts_of(values: Iterable[Any]) -> List[str]:
    """The host names of the addresses among ``values`` (an action's own
    parameters): what the administrators who created the action chose."""
    hosts: List[str] = []
    for value in values:
        if not isinstance(value, str) or "://" not in value:
            continue
        try:
            host = urlsplit(value.strip()).hostname
        except ValueError:
            continue
        if host:
            try:
                hosts.append(_ascii_host(host))
            except EgressRefused:
                continue
    return hosts


@dataclass(frozen=True)
class Destination:
    url: str
    scheme: str
    host: str
    port: int
    exempt: bool  # operator-allowed or trusted: the address may be internal


def check_url(
    url: Any,
    *,
    allow: Sequence[Tuple[str, Optional[int]]] = (),
    trusted: Sequence[str] = (),
) -> Destination:
    """The destination for ``url`` (syntax only, no network), or
    :class:`EgressRefused`."""
    invalid = EgressRefused("invalid_url")
    if not isinstance(url, str):
        raise invalid
    url = url.strip()
    if not url or len(url) > MAX_URL_LENGTH:
        raise invalid
    if any(
        ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F or ch == "\\" for ch in url
    ):
        raise invalid
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise invalid from None
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise EgressRefused("not_https")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise invalid
    raw_host = (parts.hostname or "").rstrip(".")
    if not raw_host:
        raise invalid
    host = _ascii_host(raw_host)
    port = port or (443 if scheme == "https" else 80)
    exempt = _allowed(host, port, allow) or (host in trusted)
    if not exempt:
        if scheme != "https":
            raise EgressRefused("not_https")
        if port != 443:
            raise invalid
        if _is_ip_literal(host) or not _valid_name(host):
            raise invalid
    path = parts.path or "/"
    netloc = f"[{host}]" if ":" in host else host
    if parts.port:
        netloc += f":{port}"
    rebuilt = f"{scheme}://{netloc}{path}" + (f"?{parts.query}" if parts.query else "")
    return Destination(rebuilt, scheme, host, port, exempt)


def resolve(host: str, port: int) -> List[str]:
    """Every address ``host`` resolves to. Tests replace this."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: List[str] = []
    for _family, _type, _proto, _name, sockaddr in infos:
        if sockaddr[0] not in addresses:
            addresses.append(sockaddr[0])
    return addresses


def checked_address(destination: Destination) -> str:
    """The address to connect to: the first answer, after checking that every
    answer is public (unless the destination is exempt)."""
    try:
        addresses = resolve(destination.host, destination.port)
    except (OSError, UnicodeError):
        raise EgressRefused("unreachable") from None
    if not addresses:
        raise EgressRefused("unreachable")
    if not destination.exempt and not all(is_public_address(a) for a in addresses):
        raise EgressRefused("not_allowed")
    return addresses[0]


def check_smtp(
    server: Any,
    port: Any,
    *,
    allow: Sequence[Tuple[str, Optional[int]]] = (),
    trusted: bool = False,
) -> None:
    """Whether the executor may open an SMTP connection to ``server:port``.
    ``trusted``: the settings are the instance's own (the administrators'),
    which are not judged. Otherwise: a plain host name, a mail submission port,
    every address public. (The mail library resolves the name again when it
    connects; a rebinding in that moment is not caught here: keep the executor
    on a network that cannot reach internal services, docs/executor-isolation.md.)"""
    if trusted:
        return
    try:
        number = int(port)
    except (TypeError, ValueError):
        raise EgressRefused("invalid_url") from None
    if not isinstance(server, str):
        raise EgressRefused("invalid_url")
    host = _ascii_host(server.strip().rstrip("."))
    if any(ch.isspace() or ch in "/@:\\" for ch in host) or _is_ip_literal(host):
        raise EgressRefused("invalid_url")
    if not _valid_name(host):
        raise EgressRefused("invalid_url")
    entry_allowed = any(
        entry_host == host and entry_port in (None, number)
        for entry_host, entry_port in allow
    )
    if entry_allowed:
        return
    if number not in SMTP_PORTS:
        raise EgressRefused("not_allowed")
    destination = Destination(f"smtp://{host}:{number}", "smtp", host, number, False)
    checked_address(destination)


class PinnedBackend(httpcore.NetworkBackend):
    """Connects to the address that was checked, whatever the name resolves to
    by now. TLS (SNI and the certificate check) still uses the host name."""

    def __init__(self, host: str, address: str, inner=None):
        self._host = host
        self._address = address
        self._inner = inner if inner is not None else httpcore.SyncBackend()

    def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        if host != self._host:
            raise httpcore.ConnectError("unexpected host")
        return self._inner.connect_tcp(
            self._address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    def connect_unix_socket(self, *args, **kwargs):
        raise httpcore.ConnectError("not supported")

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


def ssl_context() -> ssl.SSLContext:
    return httpx.create_ssl_context()


def _headers(extra: Optional[Dict[str, Any]], content_type: Optional[str]):
    out: List[Tuple[bytes, bytes]] = [(b"user-agent", USER_AGENT.encode())]
    seen = {"user-agent"}
    if content_type:
        out.append((b"content-type", content_type.encode()))
        seen.add("content-type")
    for name, value in (extra or {}).items():
        name_text, value_text = str(name), str(value)
        lowered = name_text.lower()
        if (
            not _HEADER_NAME.match(name_text)
            or lowered in _FORBIDDEN_HEADERS
            or any(ch in value_text for ch in "\r\n\x00")
        ):
            raise EgressRefused("invalid_url")
        if lowered in seen:
            out = [(n, v) for n, v in out if n != lowered.encode()]
        seen.add(lowered)
        out.append((lowered.encode(), value_text.encode("latin-1", "replace")))
    return out


def post(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Any = None,
    form: Optional[Dict[str, Any]] = None,
    content: Optional[bytes] = None,
    headers: Optional[Dict[str, Any]] = None,
    allow: Sequence[Tuple[str, Optional[int]]] = (),
    trusted: Sequence[str] = (),
) -> Reply:
    """POST to ``url`` under the rules above. Raises :class:`EgressRefused`."""
    destination = check_url(url, allow=allow, trusted=trusted)
    address = checked_address(destination)
    content_type = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        content_type = "application/json"
    elif form is not None:
        body = urlencode(
            {str(k): str(v) for k, v in form.items()}, doseq=False
        ).encode()
        content_type = "application/x-www-form-urlencoded"
    else:
        body = content or b""
    if len(body) > MAX_BODY_BYTES:
        raise EgressRefused("too_large")
    target = destination.url
    if params:
        target += ("&" if "?" in target else "?") + urlencode(
            {str(k): str(v) for k, v in params.items()}
        )
    pool = httpcore.ConnectionPool(
        ssl_context=ssl_context(),
        network_backend=PinnedBackend(destination.host, address),
        http1=True,
        http2=False,
        retries=0,
        max_connections=1,
    )
    try:
        with pool.stream(
            "POST",
            target,
            headers=_headers(headers, content_type),
            content=body,
            extensions={"timeout": TIMEOUTS},
        ) as response:
            status = response.status
            if 300 <= status < 400:
                raise EgressRefused("redirect_refused")
            chunks: List[bytes] = []
            size = 0
            for chunk in response.iter_stream():
                size += len(chunk)
                if size > MAX_REPLY_BYTES:
                    break  # the rest is dropped: a reply is only read for its status
                chunks.append(chunk)
    except (httpcore.TimeoutException, TimeoutError):
        raise EgressRefused("timeout") from None
    except httpcore.ProxyError:
        raise EgressRefused("unreachable") from None
    except (httpcore.NetworkError, httpcore.ProtocolError, OSError):
        raise EgressRefused("unreachable") from None
    finally:
        pool.close()
    return Reply(status, b"".join(chunks)[:MAX_REPLY_BYTES])
