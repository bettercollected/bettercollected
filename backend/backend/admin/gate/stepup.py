"""Step-up as a route attribute.

``RouteRegistry.route(path, level=..., stepup=...)`` takes one of:

* ``StepUp(max_age=300)``: the session's factor code must have been verified
  within ``max_age`` seconds (never more than ``ADMIN_STEPUP_SECONDS``). A page
  route is sent to the step-up prompt and back (``return_to``); ``/api/*`` gets
  ``403 {"error": "stepup_required"}``.
* ``ActionBound(name, parts)``: the request must carry a single-use token (header
  ``X-Stepup-Token`` or form field ``stepup_token``) issued for exactly this
  action: ``action_hash(name, *await parts(request))`` is what ``consume`` checks,
  so a token for one target or value cannot be used for another.

Enforcement is a FastAPI dependency added by the registry, so a handler cannot
forget it; it runs after the gate (session, admin and second-factor levels) and
the CSRF check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Sequence
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from backend.admin.services.stepup import action_hash

STEPUP_ATTR = "admin_stepup"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
TOKEN_HEADER = "x-stepup-token"
TOKEN_FIELD = "stepup_token"
PROMPT_PATH = "/mfa/stepup"

Parts = Callable[[Request], Awaitable[Sequence[object]]]


@dataclass(frozen=True)
class StepUp:
    max_age: int = 300
    return_to: Optional[str] = None  # a GET page to come back to after the prompt


@dataclass(frozen=True)
class ActionBound:
    name: str
    parts: Optional[Parts] = None  # values the token is bound to (default: none)

    async def hash_for(self, request: Request) -> str:
        values = await self.parts(request) if self.parts else ()
        return action_hash(self.name, *values)


def require_stepup(max_age: int = 300, return_to: Optional[str] = None) -> StepUp:
    """``@registry.route(..., stepup=require_stepup(max_age=300))``."""
    return StepUp(max_age, return_to)


class StepUpRefused(Exception):
    """Raised by the dependency; the application turns it into ``response``."""

    def __init__(self, response: Response) -> None:
        self.response = response


def _refusal(request: Request, spec) -> Response:
    if request.url.path.startswith("/api/") or not isinstance(spec, StepUp) or not spec.return_to:
        body = {"error": "stepup_required"}
        if isinstance(spec, ActionBound):
            body["action"] = spec.name
        return JSONResponse(body, status_code=403)
    return RedirectResponse(f"{PROMPT_PATH}?next={quote(spec.return_to, safe='/')}", status_code=303)


async def _token(request: Request) -> Optional[str]:
    header = request.headers.get(TOKEN_HEADER)
    if header:
        return header
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        value = (await request.form()).get(TOKEN_FIELD)
        return value if isinstance(value, str) else None
    return None


def dependency_for(spec) -> Callable:
    async def enforce(request: Request) -> None:
        portal = request.app.state.portal
        session = request.scope["state"]["session"]
        if isinstance(spec, StepUp):
            if portal.sessions.stepup_fresh(session, spec.max_age):
                return
        else:
            token = await _token(request)
            if token and await portal.stepup.consume(session, token, await spec.hash_for(request)):
                return
        raise StepUpRefused(_refusal(request, spec))

    return enforce


def check_declaration(path: str, methods: Sequence[str], stepup) -> None:
    """Registration-time rules: a step-up spec is one of the two kinds, and an
    action-bound route changes state (a GET cannot burn a token)."""
    if stepup is None:
        return
    if not isinstance(stepup, (StepUp, ActionBound)):
        raise ValueError(f"route {path}: stepup must be StepUp or ActionBound")
    if isinstance(stepup, ActionBound) and set(m.upper() for m in methods) <= SAFE_METHODS:
        raise ValueError(f"route {path}: an action-bound route must be a mutating one")


def undeclared_mutating_routes(router_routes, prefixes: Sequence[str]) -> list:
    """Mutating routes under ``prefixes`` that declare no step-up (empty is good).
    The portal's settings and task pages must all declare one."""
    missing = []
    for route in router_routes:
        if not any(route.path == p or route.path.startswith(p + "/") for p in prefixes):
            continue
        if set(route.methods) <= SAFE_METHODS:
            continue
        if getattr(route.endpoint, STEPUP_ATTR, None) is None:
            missing.append(route.path)
    return missing
