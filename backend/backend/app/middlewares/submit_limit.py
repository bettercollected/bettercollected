"""The respondent submit's rate limit, applied before its body is read.

FastAPI reads a form body (the answers and any uploads) before it runs the
route's dependencies or the route itself, so a limit inside the route comes
after the cost it is meant to avoid. Like ``received_at``, this is a pure ASGI
middleware that touches nothing but ``POST .../workspaces/{id}/forms/{id}/
response``: it counts the request against the client's budget on that form
(``services/respondent_limits.py``) and, when it is used up, answers 429 with
``Retry-After`` without reading the body at all.

It sits inside the CORS middleware, so the 429 carries the CORS headers and a
form served from another origin can read it.

A limiter that errors lets the request through (a 500 from a lock timeout on
the counters would turn a submit into a failure); only a real 429 refuses.

Nothing is counted when the client cannot be told (a proxy that is not in
TRUSTED_PROXIES), and nothing for a form that does not exist in that
workspace: the request goes on and the route answers as it always did, so
random ids create no counters.
"""

import re
from typing import Any, Awaitable, Callable, MutableMapping

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.exceptions import HTTPException
from backend.app.services.respondent_limits import fail_open
from backend.app.utils.client_ip import limit_client_ip

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]

SUBMIT_PATH = re.compile(r"/workspaces/([^/]+)/forms/([^/]+)/response/?$")


class SubmitLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive, send) -> None:
        if scope.get("type") == "http" and scope.get("method") == "POST":
            found = SUBMIT_PATH.search(scope.get("path", ""))
            if found:
                refused = await self._refusal(scope, *found.groups())
                if refused is not None:
                    await refused(scope, receive, send)
                    return
        await self.app(scope, receive, send)

    async def _refusal(self, scope: Scope, workspace_id: str, form: str):
        from backend.app.container import container

        client = limit_client_ip(Request(scope))
        if client is None:
            return None
        try:
            link = await container.workspace_form_repo().get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=form
            )
        except Exception:
            link = None  # malformed ids, a database error: the route answers
        if link is None:
            return None
        # the route needs the same form for the proof of work (CAPTCHA_ENABLED):
        # hand it over rather than read it twice
        scope.setdefault("state", {})["form_link"] = link
        try:
            # a limiter that fails lets the submit through (fail_open)
            await fail_open(
                lambda: container.respondent_limits().submit(
                    client, workspace_id, str(link.form_id)
                )
            )
        except HTTPException as refused:
            return JSONResponse(
                refused.content,
                status_code=refused.status_code,
                headers=refused.headers,
            )
        return None
