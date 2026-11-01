"""The request being served, for code deep in the services that has no
``Request`` (the SSO break-glass audit records which route was used).

The middleware binds the ASGI scope before the router runs; the router adds
the matched ``route`` to that same dict, so the route's *path template*
(``/workspaces/{workspace_id}/forms``) is available by the time authorisation
runs. Only the template is ever read: never the query string, a body or a
concrete id from the path.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional, Tuple

MAX_PATH = 200


@dataclass
class RequestContext:
    scope: dict
    # one audit row per request, however many times it is authorised
    audited: bool = False


_current: ContextVar[Optional[RequestContext]] = ContextVar(
    "bc_request_context", default=None
)


def bind_request(scope: dict):
    """Bind the request; returns the token for ``unbind_request``."""
    return _current.set(RequestContext(scope))


def unbind_request(token) -> None:
    try:
        _current.reset(token)
    except ValueError:  # a different context (never in a request task)
        pass


def current_request() -> Optional[RequestContext]:
    return _current.get()


def method_and_template(
    context: Optional[RequestContext],
) -> Tuple[Optional[str], Optional[str]]:
    """The HTTP method and the matched route's path template, or None for
    each that is unknown (outside a request, or no route matched)."""
    if context is None:
        return None, None
    scope = context.scope or {}
    method = scope.get("method")
    route = scope.get("route")
    template = getattr(route, "path", None)
    return (
        str(method).upper()[:10] if method else None,
        str(template)[:MAX_PATH] if isinstance(template, str) else None,
    )
