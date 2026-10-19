"""Gate levels and the default-deny route registry.

Every route of the admin service is registered with the level a request must
have reached; a route registered any other way fails the route-table test, and
a route whose level has no checker installed is answered 404.

Levels 0 and 1 are enforced by ``GateMiddleware``; the checkers for the
session, admin and second-factor levels are supplied by later stages through
``GateMiddleware(checkers={Level.X: async_callable(scope) -> bool})``.
"""

from enum import Enum, IntEnum
from typing import Callable, Optional

from fastapi import APIRouter, Depends
from starlette.routing import Match


class Level(IntEnum):
    NETWORK = 0  # deployment property (localhost-bound port); never a route level
    ADDRESS = 1  # Host allowlist + client address allowlist
    SESSION = 2  # a live session
    ADMIN = 3  # the session's email is a platform admin
    SECOND_FACTOR = 4  # second factor completed


class SetupStage(Enum):
    """Where a ``/setup`` route sits in the first-run wizard (see
    ``services/setup_wizard.py``). Every route under ``/setup`` must declare
    one (default deny) and nothing else may; a request outside its stage gets
    the same bare 404 as an unknown path, whatever the reason."""

    OPEN = "open"  # the token page: no confirmed factor anywhere and a valid token waits
    # a token attempt (POST): always passes the gate; the handler does the same work and
    # gives the same answer whether the token is wrong, expired, locked or setup is over
    ATTEMPT = "attempt"
    CHECKLIST = "checklist"  # after enrolment: the admin who redeemed the token, until finished


SETUP_PREFIX = "/setup"
SETUP_ATTR = "admin_setup_stage"

# answered without the address gate, for loopback peers only, no details
HEALTH_PATH = "/healthz"
LEVEL_ATTR = "admin_level"


class RouteRegistry:
    """Wraps an APIRouter: ``@registry.route(path, level=Level.ADDRESS)``."""

    def __init__(self) -> None:
        self.router = APIRouter()

    def route(
        self, path: str, *, level: Level, methods=("GET",), stepup=None,
        stepup_exempt: Optional[str] = None, setup: Optional[SetupStage] = None, **kwargs
    ) -> Callable:
        """``stepup`` (optional) is a ``StepUp`` or ``ActionBound`` from
        ``gate.stepup``; it is enforced by a dependency before the handler and
        needs a level of ``SECOND_FACTOR`` (only a completed second factor can
        have a step-up). Default deny: a mutating route under ``/settings`` or
        ``/tasks`` is refused unless it passes ``stepup`` or ``stepup_exempt``
        (a non-empty reason, for a mutating route that truly needs none)."""
        if not isinstance(level, Level) or level < Level.ADDRESS:
            raise ValueError(f"route {path}: a level of ADDRESS or above is required")
        if path == HEALTH_PATH:
            raise ValueError(f"{HEALTH_PATH} is handled by the gate itself")
        under_setup = path == SETUP_PREFIX or path.startswith(SETUP_PREFIX + "/")
        if under_setup != (setup is not None):
            raise ValueError(
                f"route {path}: routes under {SETUP_PREFIX} declare a setup stage, and only they do"
            )
        if setup in (SetupStage.OPEN, SetupStage.ATTEMPT) and level != Level.ADDRESS:
            raise ValueError(f"route {path}: the open setup stage is an ADDRESS-level page")
        if setup is SetupStage.CHECKLIST and level != Level.SECOND_FACTOR:
            raise ValueError(f"route {path}: the checklist stage needs the SECOND_FACTOR level")

        from backend.admin.gate import stepup as step

        step.check_default_deny(path, methods, stepup, stepup_exempt)
        if stepup is not None:

            step.check_declaration(path, methods, stepup)
            if level < Level.SECOND_FACTOR:
                raise ValueError(f"route {path}: step-up needs the SECOND_FACTOR level")
            kwargs["dependencies"] = [
                *(kwargs.get("dependencies") or []),
                Depends(step.dependency_for(stepup)),
            ]

        def decorator(func: Callable) -> Callable:
            setattr(func, LEVEL_ATTR, level)
            if setup is not None:
                setattr(func, SETUP_ATTR, setup)
            if stepup is not None:
                setattr(func, step.STEPUP_ATTR, stepup)
            if stepup_exempt:
                setattr(func, step.EXEMPT_ATTR, stepup_exempt)
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


def setup_stage_for_scope(routes, scope) -> Optional[SetupStage]:
    """The wizard stage of the matching route, None for a route outside it."""
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            stage = getattr(getattr(route, "endpoint", None), SETUP_ATTR, None)
            return stage if isinstance(stage, SetupStage) else None
    return None
