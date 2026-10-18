"""Request-forgery checks for every state-changing request (pure ASGI).

Runs inside the gate, after the session checks, so a request that reaches it
has already passed the address gate and carries its route level and session.

* Origin (Referer as fallback) must be one of the configured portal origins and
  ``Sec-Fetch-Site`` must not say cross-site.
* ``/api/*`` accepts JSON bodies only: a form post cannot reach a JSON endpoint.
* Routes behind the sign-in (level 2 and up) need the session's token
  (``HMAC(csrf_key, session_id)``) in ``X-CSRF-Token`` or the ``csrf_token``
  form field. Pre-sign-in forms use a signed double-submit token: the same value
  in a short-lived ``__Host-`` cookie and the hidden field.

GET, HEAD and OPTIONS never change state in this service, so they pass.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import parse_qs

from backend.admin.cookies import FORM_COOKIE, read_cookie
from backend.admin.gate.levels import Level
from backend.admin.security import csrf

log = logging.getLogger("backend.admin.csrf")

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
FORM_FIELD = "csrf_token"
FORM_TYPE = "application/x-www-form-urlencoded"
JSON_TYPE = "application/json"


def _headers(scope):
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}


class CsrfMiddleware:
    def __init__(self, app, origins, csrf_key: bytes, clock) -> None:
        self.app = app
        self.origins = tuple(origins)
        self.csrf_key = csrf_key
        self.clock = clock

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"].upper() in SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        async def refuse(status: int):
            log.warning(
                "admin csrf refused: status=%s path=%s request=%s",
                status,
                scope["path"][:100],
                scope.get("state", {}).get("request_id"),
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [(b"content-length", b"0")],
                }
            )
            await send({"type": "http.response.body", "body": b""})

        headers = _headers(scope)
        if not csrf.origin_allowed(headers, self.origins):
            await refuse(403)
            return

        media = headers.get("content-type", "").split(";")[0].strip().lower()
        has_body = headers.get("content-length", "0").strip() not in ("", "0") or (
            "transfer-encoding" in headers
        )
        if scope["path"].startswith("/api/") and has_body and media != JSON_TYPE:
            await refuse(415)
            return

        body = b""
        if media == FORM_TYPE:
            chunks, more = [], True
            while more:
                message = await receive()
                if message["type"] != "http.request":
                    return
                chunks.append(message.get("body", b""))
                more = message.get("more_body", False)
            body = b"".join(chunks)
            replayed = False

            async def receive_again():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.disconnect"}

            receive = receive_again

        supplied: Optional[str] = headers.get("x-csrf-token")
        if supplied is None and media == FORM_TYPE:
            try:
                fields = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            except UnicodeDecodeError:
                fields = {}
            values = fields.get(FORM_FIELD)
            supplied = values[0] if values else None

        state = scope.get("state", {})
        level = state.get("route_level")
        session = state.get("session")
        if level is not None and level > Level.ADDRESS:
            ok = session is not None and csrf.verify_session_token(
                self.csrf_key, session.csrf_subject, supplied
            )
        else:
            ok = csrf.verify_form_token(
                self.csrf_key, read_cookie(scope, FORM_COOKIE), supplied, self.clock
            )
        if not ok:
            await refuse(403)
            return
        await self.app(scope, receive, send)
