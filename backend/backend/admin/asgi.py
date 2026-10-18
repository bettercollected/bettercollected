"""The admin service's own application factory. Shares nothing with the public
API's app, router or container."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Mapping, Optional

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.admin.gate.csrf import CsrfMiddleware
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.middleware import Checker, GateMiddleware
from backend.admin.gate.settings import GateSettings
from backend.admin.portal import Portal

log = logging.getLogger("backend.admin")

# A bare registry for embedding and tests. The portal's own routes (sign-in,
# pages, session API) are built by ``controllers.portal.build_registry`` and used
# when a ``Portal`` is passed. Anything unregistered answers 404.
registry = RouteRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("admin service starting")
    portal = getattr(app.state, "portal", None)
    cleanup = None
    if portal is not None:
        from backend.admin.db import ensure_schema

        await ensure_schema(portal.engine)  # refuses to start on a stale schema
        await portal.startup()
        cleanup = asyncio.create_task(portal.cleanup_loop())
    try:
        yield
    finally:
        if cleanup is not None:
            cleanup.cancel()
        if portal is not None:
            await portal.engine.dispose()


async def _http_error(request: Request, exc: StarletteHTTPException) -> Response:
    return Response(status_code=exc.status_code)


async def _invalid(request: Request, exc: RequestValidationError) -> Response:
    return Response(status_code=400)


async def _failure(request: Request, exc: Exception) -> Response:
    return Response(status_code=500)  # no detail; the gate logs the type and request id


def get_admin_application(
    settings: Optional[GateSettings] = None,
    checkers: Optional[Mapping[Level, Checker]] = None,
    router_registry: Optional[RouteRegistry] = None,
    portal: Optional[Portal] = None,
):
    """The gated ASGI app (outermost callable, with the FastAPI app at
    ``.inner``). ``settings`` default to the environment; invalid values raise."""
    settings = settings or GateSettings.from_env()
    if portal is not None and router_registry is None:
        from backend.admin.controllers.portal import build_registry

        router_registry = build_registry()
    reg = router_registry or registry
    if portal is not None and checkers is None:
        checkers = portal.checkers()
    inner = FastAPI(
        title="admin",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )  # no CORS middleware, on purpose
    for route in reg.router.routes:  # flat APIRoutes, each with its level
        inner.add_api_route(
            route.path, route.endpoint, methods=sorted(route.methods), include_in_schema=False
        )
    inner.add_exception_handler(StarletteHTTPException, _http_error)
    inner.add_exception_handler(RequestValidationError, _invalid)
    inner.add_exception_handler(Exception, _failure)
    app = inner
    if portal is not None:
        inner.state.portal = portal
        app = CsrfMiddleware(
            inner, portal.settings.public_origins, portal.csrf_key, portal.clock
        )
    gated = GateMiddleware(app, settings, checkers, routes=lambda: inner.router.routes)
    gated.inner = inner
    return gated
