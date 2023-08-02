"""Application implementation - ASGI."""
import logging

import auth
import sentry_sdk
from auth.app.container import container
from auth.app.exceptions import (
    HTTPException,
    http_exception_handler,
)
from auth.app.exceptions.http import not_found_error_handler
from auth.app.router import root_api_router
from auth.app.services.database_service import close_db, init_db
from auth.config import settings
from elasticapm.contrib.starlette import make_apm_client, ElasticAPM
from fastapi import FastAPI
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration

from common.exceptions import NotFoundError

log = logging.getLogger(__name__)


async def on_startup():
    """Define FastAPI startup event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#startup-event

    """
    log.debug("Execute FastAPI startup event handler.")
    database_client = container.database_client()
    await init_db(database_client)


async def on_shutdown():
    """Define FastAPI shutdown event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#shutdown-event

    """
    log.debug("Execute FastAPI shutdown event handler.")
    await container.http_client().aclose()

    database_client = container.database_client()
    await close_db(database_client)


apm = make_apm_client()


def get_application():
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    log.debug("Initialize FastAPI application node.")
    container.wire(packages=[auth.app])
    sentry_settings = settings.sentry_settings

    sentry_sdk.init(
        dsn=sentry_settings.DSN,
        max_breadcrumbs=50,
        debug=sentry_settings.DEBUG,
        release=settings.API_VERSION,
        environment=settings.API_ENVIRONMENT,
        attach_stacktrace=True,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production,
        traces_sample_rate=1.0,
        integrations=[
            AsyncioIntegration(),
            HttpxIntegration(),
            LoguruIntegration(),
        ],
    )

    app = FastAPI(
        title=settings.API_TITLE,
        debug=settings.DEBUG,
        version=settings.API_VERSION,
        docs_url=settings.API_ROOT_PATH + "/docs",
        openapi_url=settings.API_ROOT_PATH + "/openapi.json",
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )
    log.debug("Add application routes.")
    app.include_router(root_api_router)
    log.debug("Register global exception handler for custom HTTPException.")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(NotFoundError, not_found_error_handler)
    if settings.apm_settings.service_name and settings.apm_settings.server_url:
        app.add_middleware(ElasticAPM, client=apm)
    return app
