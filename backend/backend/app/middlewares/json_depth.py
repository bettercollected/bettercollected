"""A JSON request body nested too deeply is refused before anything parses it.

``json.loads`` recurses once per nesting level and, on the interpreter the
backend runs on, fails with a ``RecursionError`` somewhat under a thousand
levels: a body of a few KB of brackets. Every JSON reader in the API (FastAPI's
own body parsing, the public API, the operations routes, the idempotency
fingerprint, SCIM, MCP) sits behind this pure ASGI middleware, which scans the
body of a JSON-like request as it arrives (``utils/json_depth.py``, iterative,
a counter and a flag of state) and answers 422 ``body_too_deep`` when it nests
deeper than ``MAX_JSON_DEPTH``.

What it looks at: POST, PUT, PATCH and DELETE with ``application/json``,
``application/*+json``, ``text/plain`` or no content type (several routes read
the raw body whatever the header says). Form posts (urlencoded or multipart,
uploads included) are not JSON documents and are never touched here; the JSON
a form field carries is checked where the field is parsed.

Two phases, whatever the size of the body:

1. Up to ``MAX_BUFFERED_BYTES`` the body is read here before the route runs,
   scanned as it comes, and replayed to the route unchanged; a deep one is
   refused at once without reading the rest.
2. Beyond that (a body that declares more, or a chunked body that grows past
   it) the pieces go straight on to the route, each scanned on the way, so the
   route's own size limit answers as it always did (a 413 without the body
   being read, or when its running cap is passed) and nothing more is held
   here. If a piece takes the nesting past the limit the route is told the
   client has gone, whatever it then answers is dropped, and the 422 is sent
   in its place. A route that has already started its answer (its own 413,
   say) keeps it.

Padding before or after the nesting changes nothing: the scan sees every byte
that the route could read.

It sits inside the CORS middleware, so the refusal can be read from another
origin, and after the respondent submit's rate limit, which counts a request
before its body is read.
"""

from typing import Any, Awaitable, Callable, List, MutableMapping, Optional

from starlette.responses import JSONResponse

from backend.app.utils.json_depth import CODE, MESSAGE, DepthScanner

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]

# The most of a body held here before the route runs: as much as the largest
# JSON a route accepts (a form spec or an operations request is at most 1 MiB,
# a directory event 1 MB, a draft 320 KiB). It is read before the caller is
# authenticated, so it is not more than that.
MAX_BUFFERED_BYTES = 1024 * 1024

BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _carries_json(scope: Scope) -> Optional[int]:
    """None when this request is not one that may carry a JSON document;
    otherwise its declared length (-1 when it declares none: chunked)."""
    if scope.get("method") not in BODY_METHODS:
        return None
    declared: Optional[int] = None
    content_type = b""
    chunked = False
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            declared = int(value) if value.strip().isdigit() else None
        elif name == b"content-type":
            content_type = value
        elif name == b"transfer-encoding":
            chunked = True
    if declared == 0 or (declared is None and not chunked):
        return None
    media = content_type.split(b";", 1)[0].strip().lower()
    if not (
        media in (b"", b"application/json", b"text/plain")
        or (media.startswith(b"application/") and media.endswith(b"+json"))
    ):
        return None
    return -1 if declared is None else declared


class JsonDepthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive, send) -> None:
        declared = _carries_json(scope) if scope.get("type") == "http" else None
        if declared is None:
            await self.app(scope, receive, send)
            return

        scanner = DepthScanner()
        chunks: List[bytes] = []
        size = 0
        more = True
        ended: Optional[MutableMapping[str, Any]] = None  # a message that is not body
        # phase 1: hold the body (and scan it) while it is within the cap
        if declared <= MAX_BUFFERED_BYTES:
            while more and size <= MAX_BUFFERED_BYTES:
                message = await receive()
                if message["type"] != "http.request":
                    ended = message
                    break
                chunk = message.get("body", b"")
                if chunk:
                    if scanner.feed(chunk):
                        await self._refusal(scope)(scope, receive, send)
                        return
                    chunks.append(chunk)
                    size += len(chunk)
                more = message.get("more_body", False)
        held = b"".join(chunks)
        chunks.clear()

        # (nothing to replay when phase 1 was skipped)
        replayed = declared > MAX_BUFFERED_BYTES
        violated = False
        started = False

        async def scanning_receive():
            nonlocal replayed, violated
            if violated:
                return {"type": "http.disconnect"}
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": held, "more_body": more}
            if ended is not None:
                return ended
            message = await receive()
            if message["type"] == "http.request" and scanner.feed(message.get("body", b"")):
                # too deep: the route sees the client go away
                violated = True
                return {"type": "http.disconnect"}
            return message

        async def guarded_send(message) -> None:
            nonlocal started
            if violated:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, scanning_receive, guarded_send)
        except Exception:
            if not violated:
                raise
        if violated and not started:
            await self._refusal(scope)(scope, receive, send)

    @staticmethod
    def _refusal(scope: Scope) -> JSONResponse:
        payload = {"code": CODE, "message": MESSAGE}
        # the MCP endpoint's own errors are {"error": ...}
        if "mcp" in scope.get("path", "").split("/"):
            payload["error"] = MESSAGE
        return JSONResponse(payload, status_code=422)
