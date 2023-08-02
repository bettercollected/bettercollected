"""Application implementation - ASGI."""
import logging

import sentry_sdk
from elasticapm.contrib.starlette import make_apm_client, ElasticAPM
from fastapi import FastAPI
from google.auth.exceptions import RefreshError
from httplib2 import ServerNotFoundError
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration

from googleform.app.containers import Container
from googleform.app.exceptions import (
    HTTPException,
    http_exception_handler,
)
from googleform.app.exceptions.http import timeout_error_handler, refresh_error_handler, server_not_found_error_handler
from googleform.app.router import root_api_router
from googleform.app.services.database_service import close_db, init_db
from googleform.app.services.migration_service import (
    migrate_credentials_to_include_user_id,
)
from googleform.app.utils import AiohttpClient, RedisClient
from googleform.config import settings

log = logging.getLogger(__name__)


async def on_startup():
    """Define FastAPI startup event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#startup-event

    """
    log.debug("Execute FastAPI startup event handler.")
    if settings.USE_REDIS:
        await RedisClient.open_redis_client()

    AiohttpClient.get_aiohttp_client()


async def on_shutdown():
    """Define FastAPI shutdown event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#shutdown-event

    """
    log.debug("Execute FastAPI shutdown event handler.")
    # Gracefully close utilities.
    if settings.USE_REDIS:
        await RedisClient.close_redis_client()
    Container.executor = None
    await AiohttpClient.close_aiohttp_client()


apm = make_apm_client()


def get_application():
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
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
    app.add_exception_handler(TimeoutError, timeout_error_handler)
    app.add_exception_handler(RefreshError, refresh_error_handler)
    app.add_exception_handler(ServerNotFoundError, server_not_found_error_handler)
    if settings.apm_settings.service_name and settings.apm_settings.server_url:
        app.add_middleware(ElasticAPM, client=apm)
    return app
