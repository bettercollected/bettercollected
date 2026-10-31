"""When a submission reached the backend, stamped before its body is read.

FastAPI reads a form body (the answers and any uploads) before it runs the
route's dependencies or the route itself, so only a middleware sees the
request on arrival. This one is pure ASGI and touches nothing but
``POST .../workspaces/{id}/forms/{id}/response``: it stores the time in
``scope["state"]["received_at"]`` (``request.state.received_at``), which the
close-date gate judges the submission at (services/form_availability.py).

The time is when the backend received the request. Behind a proxy that
buffers request bodies the backend gets the request only once the upload has
finished there, so the stamp then means "upload finished".
"""

import re
from typing import Any, Awaitable, Callable, MutableMapping

from backend.app.services import form_availability

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]

SUBMIT_PATH = re.compile(r"/workspaces/[^/]+/forms/[^/]+/response/?$")


class ReceivedAtMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive, send) -> None:
        if (
            scope.get("type") == "http"
            and scope.get("method") == "POST"
            and SUBMIT_PATH.search(scope.get("path", ""))
        ):
            scope.setdefault("state", {})["received_at"] = form_availability.now()
        await self.app(scope, receive, send)
