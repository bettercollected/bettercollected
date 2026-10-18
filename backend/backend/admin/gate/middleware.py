"""The outermost layer of the admin service (pure ASGI).

Order: request id and security headers on every response -> /healthz
(loopback peers and the admin network's gateway only) -> Host allowlist -> client address allowlist ->
body cap and content type -> route level (default deny) -> the application.
A request that fails the first two gates gets a bare 404 and never reaches
anything else: no routing, no application code, no database.
"""

import logging
import re
import time
import uuid
from typing import Awaitable, Callable, Mapping, Optional

from common.utils.client_ip import parse_address, resolve_client_ip

from backend.admin.gate.levels import HEALTH_PATH, Level, level_for_scope
from backend.admin.gate.settings import GateSettings
from backend.admin.headers import with_security_headers

log = logging.getLogger("backend.admin.gate")

MAX_BODY_BYTES = 64 * 1024
ALLOWED_CONTENT_TYPES = ("application/x-www-form-urlencoded", "application/json")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")

Checker = Callable[[dict], Awaitable[bool]]


class _BodyTooLarge(BaseException):  # passes the application's own Exception handlers
    pass


def sanitize(value: str, limit: int = 200) -> str:
    return _CONTROL.sub("", value)[:limit]


class _LogLimiter:
    """At most ``burst`` lines per ``period`` seconds; the rest are counted."""

    def __init__(self, burst: int = 5, period: float = 10.0) -> None:
        self.burst, self.period = burst, period
        self.window_start = float("-inf")
        self.count = 0
        self.suppressed = 0

    def allow(self) -> Optional[int]:
        """None when the line is dropped, else the number dropped before it."""
        now = time.monotonic()
        if now - self.window_start >= self.period:
            self.window_start, self.count = now, 0
        if self.count >= self.burst:
            self.suppressed += 1
            return None
        self.count += 1
        dropped, self.suppressed = self.suppressed, 0
        return dropped


def _header_values(scope, name: bytes):
    return [v.decode("latin-1") for k, v in scope.get("headers", ()) if k == name]


class GateMiddleware:
    def __init__(
        self,
        app,
        settings: GateSettings,
        checkers: Optional[Mapping[Level, Checker]] = None,
        routes=None,
    ) -> None:
        self.app = app
        self.settings = settings
        self.checkers = dict(checkers or {})
        self._routes = routes  # a list of routes or a callable returning one
        self._limiter = _LogLimiter()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":  # websockets and anything else: not served
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def guarded_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message = dict(message)
                headers = with_security_headers(message.get("headers", ()))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        async def respond(status: int, headers=(), body: bytes = b""):
            await guarded_send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [(b"content-length", str(len(body)).encode()), *headers],
                }
            )
            await guarded_send({"type": "http.response.body", "body": body})

        try:
            await self._handle(scope, receive, guarded_send, respond, request_id)
        except _BodyTooLarge:
            if not started:
                await respond(413)
        except Exception as exc:  # never a trace or a body to the client
            log.error(
                "admin request failed: %s (request %s)", type(exc).__name__, request_id
            )
            if not started:
                await respond(500)

    def _deny(self, scope, peer, client, reason, request_id):
        dropped = self._limiter.allow()
        if dropped is None:
            return
        xff = sanitize(", ".join(_header_values(scope, b"x-forwarded-for")))
        log.warning(
            "admin gate denied: reason=%s peer=%s client=%s xff=%r method=%s path=%s request=%s%s",
            reason,
            sanitize(str(peer), 64),
            sanitize(str(client), 64),
            xff,
            sanitize(scope.get("method", ""), 16),
            sanitize(scope.get("path", ""), 200),
            request_id,
            f" suppressed={dropped}" if dropped else "",
        )

    async def _unauthenticated(self, scope, respond) -> None:
        """401 JSON for ``/api/*``, else a 303 to the sign-in page (or the
        second-factor page). The reason is internal: it is logged at debug
        level by the checker, never sent."""
        if scope["path"].startswith("/api/"):
            await respond(
                401,
                [(b"content-type", b"application/json")],
                b'{"error":"unauthenticated"}',
            )
            return
        reason = scope["state"].get("deny_reason")
        target = b"/mfa" if reason == "mfa_required" else b"/login"
        await respond(303, [(b"location", target)])

    async def _handle(self, scope, receive, send, respond, request_id):
        method = scope["method"].upper()
        path = scope["path"]
        peer = scope["client"][0] if scope.get("client") else None
        peer_addr = parse_address(peer)

        if path == HEALTH_PATH:
            if (
                method in ("GET", "HEAD")
                and peer_addr is not None
                and (peer_addr.is_loopback or peer_addr == self.settings.edge_gateway)
            ):
                body = b"" if method == "HEAD" else b"ok"
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            (b"content-type", b"text/plain; charset=utf-8"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
            else:
                self._deny(scope, peer, None, "healthz-not-loopback", request_id)
                await respond(404)
            return

        # level 1a: Host allowlist (DNS rebinding)
        hosts = _header_values(scope, b"host")
        if len(hosts) != 1 or hosts[0].strip().lower() not in self.settings.allowed_hosts:
            self._deny(scope, peer, None, "host", request_id)
            await respond(404)
            return

        # level 1b: client address allowlist
        client = resolve_client_ip(
            peer,
            _header_values(scope, b"x-forwarded-for"),
            None,
            self.settings.trusted_proxies,
            None,
        )
        scope["state"]["client_ip"] = client
        address = parse_address(client)
        if address is None or not any(
            address.version == n.version and address in n
            for n in self.settings.allowed_ips
        ):
            self._deny(scope, peer, client, "address", request_id)
            await respond(404)
            return

        # body cap and content type
        length_values = _header_values(scope, b"content-length")
        has_body = False
        if length_values:
            if len(length_values) != 1 or not length_values[0].strip().isdigit():
                await respond(400)
                return
            declared = int(length_values[0])
            if declared > MAX_BODY_BYTES:
                await respond(413)
                return
            has_body = declared > 0
        if _header_values(scope, b"transfer-encoding"):
            has_body = True
        if has_body:
            types = _header_values(scope, b"content-type")
            media = types[0].split(";")[0].strip().lower() if len(types) == 1 else ""
            if media not in ALLOWED_CONTENT_TYPES:
                await respond(415)
                return

        # route level, default deny
        routes = self._routes() if callable(self._routes) else (self._routes or [])
        level = level_for_scope(routes, scope)
        if level is None:
            await respond(404)
            return
        scope["state"]["route_level"] = level
        if level > Level.ADDRESS:
            # every level up to the route's, in order; the first failure ends it
            for step in Level:
                if step <= Level.ADDRESS or step > level:
                    continue
                checker = self.checkers.get(step)
                if checker is None:
                    await respond(404)
                    return
                if not await checker(scope):
                    await self._unauthenticated(scope, respond)
                    return

        received = 0

        async def capped_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY_BYTES:
                    raise _BodyTooLarge()
            return message

        await self.app(scope, capped_receive, send)
