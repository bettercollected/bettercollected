"""Application implementation - ASGI."""
import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi_utils.timing import add_timing_middleware
from loguru import logger
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration

from typeform.app.container import container
from typeform.app.exceptions import HTTPException, http_exception_handler
from typeform.app.handlers import init_logging
from typeform.app.middlewares import include_middlewares
from typeform.app.router import root_api_router
from typeform.app.services.database_service import close_db, init_db
from typeform.app.services.migration_service import (
    migrate_credentials_to_include_user_id,
)
from typeform.config import settings

log = logging.getLogger(__name__)


async def on_startup():
    """Define FastAPI startup event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#startup-event

    """
    log.debug("Execute FastAPI startup event handler.")


async def on_shutdown():
    """Define FastAPI shutdown event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#shutdown-event

    """
    log.debug("Execute FastAPI shutdown event handler.")
    await container.http_client().aclose()
    # Gracefully close utilities.


def get_application():
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    init_logging()
    log.debug("Initialize FastAPI application node.")
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
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        version=settings.VERSION,
        docs_url=settings.API_ROOT_PATH + "/docs",
        openapi_url=settings.API_ROOT_PATH + "/openapi.json",
        on_startup=[on_startup, init_db, migrate_credentials_to_include_user_id],
        on_shutdown=[on_shutdown, close_db],
    )
    log.debug("Add application routes.")
    app.include_router(root_api_router)
    log.debug("Register global exception handler for custom HTTPException.")
    app.add_exception_handler(HTTPException, http_exception_handler)

    include_middlewares(app)
    add_timing_middleware(app, record=logger.info, prefix="app", exclude="untimed")

    return app
