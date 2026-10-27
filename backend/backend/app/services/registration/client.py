"""The outgoing calls of the registration feature: POST a JSON body to a
service's address (and, for an Objects API service, GET its object list to
look for an object we may already have created), under the rules of
``services/safe_http.py``.

- https only, the default port only, no credentials in the address;
- the host is resolved at **every** connection and every answer must be a
  public address; the connection goes to the address checked, so a name that
  turned private since the service was saved (or rebinds between lookups) is
  refused (``not_allowed``);
- **no redirects**: a 3xx is a permanent failure (``redirect_refused``), so the
  credential header never follows a redirect anywhere;
- the request body is capped (``MAX_BODY_BYTES``), the reply is read up to
  ``MAX_REPLY_BYTES`` and dropped (a caller that needs a little of it, the
  Objects API's, asks for it and gets at most that many bytes), connect,
  read, write and total time are bounded;
- no cookies, no proxy settings, no compression, a fixed ``User-Agent``.

Errors carry one of our codes and the HTTP status, never the destination's
text, the address or the secret. Tests replace ``resolve``, ``network_backend``
and ``ssl_context`` of this module; no setting does.
"""

from __future__ import annotations

import asyncio
import base64
import re
import ssl
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple
from urllib.parse import quote, unquote, urlencode, urlsplit

import httpcore

from backend.app.services import safe_http
from backend.app.services.safe_http import PinnedBackend, resolve  # noqa: F401

MAX_BODY_BYTES = 20 * 1024 * 1024
MAX_REPLY_BYTES = 64 * 1024
# a lookup that hits returns the whole stored record, which can be large; the
# reply is streamed, parsed for the little we need and dropped
MAX_LOOKUP_REPLY_BYTES = 2 * 1024 * 1024
TIMEOUTS = {"connect": 5.0, "read": 20.0, "write": 30.0, "pool": 5.0}
TOTAL_TIMEOUT_S = 60.0
MAX_RETRY_AFTER_S = 3600
MAX_PATH_LENGTH = 255
USER_AGENT = b"bettercollected-registration/1"
_SAFE_PATH = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$")
_TRANSIENT_STATUS = {408, 429}
_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,100}$")


class SendFailed(Exception):
    """``code`` is one of ``invalid_url``, ``not_allowed``, ``unreachable``,
    ``timeout``, ``tls_error``, ``redirect_refused``, ``http_4xx``,
    ``http_5xx``, ``too_large``, ``config_invalid``. ``permanent``: retrying cannot help.
    """

    def __init__(
        self,
        code: str,
        *,
        permanent: bool,
        http_status: Optional[int] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(code)
        self.code = code
        self.permanent = permanent
        self.http_status = http_status
        self.retry_after = retry_after


@dataclass(frozen=True)
class Target:
    """Where and how to send. ``auth``: ``none``, ``header`` (``auth_name`` is
    the header, ``secret`` its value), ``basic`` (``auth_name`` the user) or
    ``token`` (``Authorization: Token <secret>``)."""

    base_url: str
    path: str = ""
    auth: str = "none"
    auth_name: Optional[str] = None
    secret: Optional[str] = field(default=None, repr=False)


_RESERVED_HEADERS = {
    "host",
    "transfer-encoding",
    "connection",
    "keep-alive",
    "upgrade",
    "te",
    "trailer",
    "idempotency-key",
    "user-agent",
    "cookie",
    "set-cookie",
}


def reserved_header(name: str) -> bool:
    """Headers the client sets itself or that change how a request is routed or
    framed: never carriers of a secret."""
    low = name.strip().lower()
    return (
        low in _RESERVED_HEADERS
        or low.startswith(("content-", "proxy-", "accept", ":"))
        or low.startswith("x-forwarded-")
    )


def path_problem(path: str) -> Optional[str]:
    """Why ``path`` may not be appended to a service address, or None. No
    ``..`` (also encoded), no scheme, host, query or fragment."""
    if not isinstance(path, str) or len(path) > MAX_PATH_LENGTH:
        return "too_long"
    if not _SAFE_PATH.match(path) or path.startswith("//"):
        return "not_a_path"
    decoded = unquote(unquote(path))
    if ".." in decoded or "\\" in decoded or "?" in decoded or "#" in decoded:
        return "not_a_path"
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
        return "not_a_path"  # looks like a scheme
    return None


def base_path_problem(url: str) -> bool:
    """Whether the path of a service's base address has a dot segment, or an
    encoded (once or twice) dot, slash or backslash: fails closed, like
    ``path_problem``."""
    for segment in urlsplit(url.strip()).path.split("/"):
        decoded = unquote(unquote(segment))
        if ".." in decoded or decoded == "." or "/" in decoded or "\\" in decoded:
            return True
    return False


def full_url(base_url: str, path: str) -> str:
    if path_problem(path):
        raise SendFailed("invalid_url", permanent=True)
    base = base_url.strip()
    relative = path.lstrip("/")
    return base.rstrip("/") + "/" + relative if relative else base


def network_backend(host: str, address: str) -> httpcore.AsyncNetworkBackend:
    """The connection for one request. Tests replace this."""
    return PinnedBackend(host, address)


def ssl_context() -> ssl.SSLContext:
    """Tests replace this (a throw-away CA)."""
    return safe_http.ssl_context()


def _auth_headers(target: Target):
    try:
        if target.auth == "header" and target.auth_name and target.secret is not None:
            name = target.auth_name.encode("ascii")
            value = target.secret.encode("latin-1")
            if (
                not _HEADER_NAME.match(target.auth_name)
                or reserved_header(target.auth_name)
                or re.search(rb"[\r\n\x00]", value)
            ):
                raise ValueError
            return [(name, value)]
    except (UnicodeError, ValueError):
        raise SendFailed("config_invalid", permanent=True)
    if target.auth == "token" and target.secret:
        try:
            value = target.secret.encode("ascii")
        except UnicodeError:
            raise SendFailed("config_invalid", permanent=True)
        if re.search(rb"[\s\x00-\x1f\x7f]", value):
            raise SendFailed("config_invalid", permanent=True)
        return [(b"Authorization", b"Token " + value)]
    if target.auth == "token":
        raise SendFailed("config_invalid", permanent=True)
    if target.auth == "basic" and target.auth_name is not None:
        raw = f"{target.auth_name}:{target.secret or ''}".encode("utf-8")
        return [(b"Authorization", b"Basic " + base64.b64encode(raw))]
    return []


def _retry_after(headers) -> Optional[int]:
    value = safe_http.header_value(headers, b"retry-after")
    if value and value.isdigit():
        return min(int(value), MAX_RETRY_AFTER_S)
    return None


def _caused_by_tls(exc: BaseException) -> bool:
    seen = 0
    while exc is not None and seen < 8:
        if isinstance(exc, ssl.SSLError):
            return True
        exc = exc.__cause__ or exc.__context__
        seen += 1
    return False


@dataclass(frozen=True)
class Reply:
    """A 2xx answer. ``body`` is empty unless the caller asked to keep the
    reply; ``truncated``: the reply was longer than ``MAX_REPLY_BYTES`` (the
    body then holds only what was read, so a caller must not parse it)."""

    status: int
    body: bytes = b""
    truncated: bool = False


async def _request_once(
    method: str,
    url: str,
    host: str,
    address: str,
    body: Optional[bytes],
    headers,
    keep_reply: bool,
    max_reply: int,
) -> Reply:
    async with httpcore.AsyncConnectionPool(
        ssl_context=ssl_context(),
        network_backend=network_backend(host, address),
        max_connections=1,
        retries=0,
        http2=False,
    ) as pool:
        async with pool.stream(
            method,
            url,
            headers=headers,
            content=body,
            extensions={"timeout": TIMEOUTS},
        ) as response:
            status = response.status
            if 300 <= status < 400:
                raise SendFailed("redirect_refused", permanent=True, http_status=status)
            if status >= 400:
                transient = status >= 500 or status in _TRANSIENT_STATUS
                raise SendFailed(
                    "http_5xx" if status >= 500 else "http_4xx",
                    permanent=not transient,
                    http_status=status,
                    retry_after=_retry_after(response.headers),
                )
            # the reply is not kept (unless asked to, up to the cap): read a
            # little, then drop the connection
            total = 0
            kept = bytearray()
            truncated = False
            async for chunk in response.aiter_stream():
                total += len(chunk)
                if total > max_reply:
                    truncated = True
                    break
                if keep_reply:
                    kept += chunk
            return Reply(status, bytes(kept) if not truncated else b"", truncated)


async def request(
    target: Target,
    method: str,
    *,
    body: Optional[bytes] = None,
    query: Optional[Sequence[Tuple[str, str]]] = None,
    extra_headers: Sequence[Tuple[bytes, bytes]] = (),
    idempotency_key: Optional[str] = None,
    keep_reply: bool = False,
    max_reply: Optional[int] = None,
) -> Reply:
    """One request to ``target`` (``POST`` with ``body``, or ``GET``). Returns
    the 2xx :class:`Reply` or raises :class:`SendFailed`. ``query`` pairs are
    encoded here; callers build them from validated configuration and our own
    ids only, never from a respondent's input."""
    if method not in ("POST", "GET"):
        raise SendFailed("config_invalid", permanent=True)
    if body is not None and len(body) > MAX_BODY_BYTES:
        raise SendFailed("too_large", permanent=True)
    try:
        if base_path_problem(target.base_url):
            raise SendFailed("invalid_url", permanent=True)
        # the stored base itself carries no query, whatever we append below
        safe_http.checked_https_url(target.base_url, allow_query=False)
        url = full_url(target.base_url, target.path)
        if query:
            url += "?" + urlencode(list(query), quote_via=quote)
        url, host = safe_http.checked_https_url(url, allow_query=bool(query))
    except safe_http.UrlRefused:
        raise SendFailed("invalid_url", permanent=True)
    headers = [
        (b"User-Agent", USER_AGENT),
        (b"Accept", b"application/json" if keep_reply else b"*/*"),
        (b"Accept-Encoding", b"identity"),
    ]
    if body is not None:
        headers += [
            (b"Content-Type", b"application/json"),
            (b"Content-Length", str(len(body)).encode()),
        ]
    if idempotency_key is not None:
        headers.append((b"Idempotency-Key", idempotency_key.encode("ascii", "ignore")))
    headers += [*extra_headers, *_auth_headers(target)]

    async def run() -> Reply:
        try:
            address = await safe_http.public_address(host, lambda h, p: resolve(h, p))
        except safe_http.AddressRefused as refused:
            if refused.code == "not_allowed":
                raise SendFailed("not_allowed", permanent=True)
            raise SendFailed("unreachable", permanent=False)
        try:
            return await _request_once(
                method,
                url,
                host,
                address,
                body,
                headers,
                keep_reply,
                max_reply or MAX_REPLY_BYTES,
            )
        except SendFailed:
            raise
        except httpcore.TimeoutException:
            raise SendFailed("timeout", permanent=False)
        except (httpcore.NetworkError, httpcore.ProtocolError, ssl.SSLError) as exc:
            if _caused_by_tls(exc):
                raise SendFailed("tls_error", permanent=False)
            raise SendFailed("unreachable", permanent=False)

    try:
        return await asyncio.wait_for(run(), TOTAL_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise SendFailed("timeout", permanent=False)


async def post_json(target: Target, body: bytes, *, idempotency_key: str) -> int:
    """POST ``body`` and return the 2xx status, or raise :class:`SendFailed`."""
    reply = await request(target, "POST", body=body, idempotency_key=idempotency_key)
    return reply.status
