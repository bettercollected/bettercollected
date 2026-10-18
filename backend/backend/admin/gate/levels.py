"""Gate levels and the default-deny route registry.

Every route of the admin service is registered with the level a request must
have reached; a route registered any other way fails the route-table test, and
a route whose level has no checker installed is answered 404.

Levels 0 and 1 are enforced by ``GateMiddleware``; the checkers for the
session, admin and second-factor levels are supplied by later stages through
``GateMiddleware(checkers={Level.X: async_callable(scope) -> bool})``.
"""

from enum import IntEnum
from typing import Callable, Optional

from fastapi import APIRouter
from starlette.routing import Match


class Level(IntEnum):
    NETWORK = 0  # deployment property (localhost-bound port); never a route level
    ADDRESS = 1  # Host allowlist + client address allowlist
    SESSION = 2  # a live session
    ADMIN = 3  # the session's email is a platform admin
    SECOND_FACTOR = 4  # second factor completed


# answered without the address gate, for loopback peers only, no details
HEALTH_PATH = "/healthz"
LEVEL_ATTR = "admin_level"


class RouteRegistry:
    """Wraps an APIRouter: ``@registry.route(path, level=Level.ADDRESS)``."""

    def __init__(self) -> None:
        self.router = APIRouter()

    def route(self, path: str, *, level: Level, methods=("GET",), **kwargs) -> Callable:
        if not isinstance(level, Level) or level < Level.ADDRESS:
            raise ValueError(f"route {path}: a level of ADDRESS or above is required")
        if path == HEALTH_PATH:
            raise ValueError(f"{HEALTH_PATH} is handled by the gate itself")

        def decorator(func: Callable) -> Callable:
            setattr(func, LEVEL_ATTR, level)
            self.router.add_api_route(
                path,
                func,
                methods=list(methods),
                include_in_schema=False,
                **kwargs,
            )
            return func

        return decorator


def level_for_scope(routes, scope) -> Optional[Level]:
    """The level the matching route requires; None when no route fully matches
    (unknown path or method) or the route carries no level (denied)."""
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            level = getattr(getattr(route, "endpoint", None), LEVEL_ATTR, None)
            return level if isinstance(level, Level) else None
    return None
