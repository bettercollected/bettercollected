"""A JSON request body nested too deeply is refused before anything parses it.

``json.loads`` recurses once per nesting level and, on the interpreter the
backend runs on, fails with a ``RecursionError`` somewhat under a thousand
levels: a body of a few KB of brackets. Every JSON reader in the API (FastAPI's
own body parsing, the public API, the operations routes, the idempotency
fingerprint, SCIM, MCP) sits behind this pure ASGI middleware, which reads the
body of a JSON-like request once, scans it iteratively (``utils/json_depth.py``)
and answers 422 ``body_too_deep`` when it nests deeper than ``MAX_JSON_DEPTH``.
The body is handed on unchanged otherwise.

What it reads: POST, PUT, PATCH and DELETE with ``application/json``,
``application/*+json``, ``text/plain`` or no content type (several routes read
the raw body whatever the header says). Form posts (urlencoded or multipart,
uploads included) are not JSON documents and are never buffered here; the JSON
a form field carries is checked where the field is parsed.

It reads at most ``MAX_SCANNED_BYTES`` (a request that declares more is handed
on untouched, so the route's own size limit answers 413 without the body being
read here, and a longer chunked body is checked up to that point). Where this
does not look, the places that parse a body also turn a ``RecursionError`` into
the same answer.

It sits inside the CORS middleware, so the refusal can be read from another
origin, and after the respondent submit's rate limit, which counts a request
before its body is read.
"""

from typing import Any, Awaitable, Callable, List, MutableMapping, Optional

from starlette.responses import JSONResponse

from backend.app.utils.json_depth import CODE, MESSAGE, too_deep

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]

# The most the body of a request is read here: as much as the largest JSON a
# route accepts (a form spec or an operations request is at most 1 MiB, a
# directory event 1 MB, a draft 320 KiB). A route answers anything bigger with
# its own 413, and this is read before the caller is authenticated, so it is
# not more than that.
MAX_SCANNED_BYTES = 1024 * 1024

BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _carries_json(scope: Scope) -> bool:
    """Is this request one that may carry a JSON document?"""
    if scope.get("method") not in BODY_METHODS:
        return False
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
    if declared is not None and (declared == 0 or declared > MAX_SCANNED_BYTES):
        return False
    if declared is None and not chunked:
        return False
    media = content_type.split(b";", 1)[0].strip().lower()
    return (
        media in (b"", b"application/json", b"text/plain")
        or (media.startswith(b"application/") and media.endswith(b"+json"))
    )


class JsonDepthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive, send) -> None:
        if scope.get("type") != "http" or not _carries_json(scope):
            await self.app(scope, receive, send)
            return

        chunks: List[bytes] = []
        size = 0
        ended: Optional[MutableMapping[str, Any]] = None  # a message that is not body
        more = True
        while more and size <= MAX_SCANNED_BYTES:
            message = await receive()
            if message["type"] != "http.request":
                ended = message
                break
            chunk = message.get("body", b"")
            if chunk:
                chunks.append(chunk)
                size += len(chunk)
            more = message.get("more_body", False)

        body = b"".join(chunks)
        chunks.clear()
        if too_deep(body):
            await self._refusal(scope)(scope, receive, send)
            return

        # Hand the body on: what was read, then whatever has not been read yet
        # (a body past the cap) and the disconnect.
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": more}
            if ended is not None:
                return ended
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    def _refusal(scope: Scope) -> JSONResponse:
        payload = {"code": CODE, "message": MESSAGE}
        # the MCP endpoint's own errors are {"error": ...}
        if "mcp" in scope.get("path", "").split("/"):
            payload["error"] = MESSAGE
        return JSONResponse(payload, status_code=422)
