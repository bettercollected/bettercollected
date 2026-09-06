"""Application implementation - ASGI."""

import json
import logging

from elasticapm.contrib.starlette import make_apm_client, ElasticAPM
from fastapi import FastAPI

from googleform.app.containers import Container
from googleform.app.exceptions import (
    HTTPException,
    http_exception_handler,
)
from googleform.app.exceptions.http import (
    timeout_error_handler,
    refresh_error_handler,
    server_not_found_error_handler,
)
from googleform.app.router import root_api_router
from googleform.app.services.database_service import close_db, init_db
from common.db import check_postgres_at_startup, dispose_engine
from googleform.app.services.migration_service import (
    migrate_credentials_to_include_user_id,
)
from googleform.app.utils import AiohttpClient
from googleform.config import settings

log = logging.getLogger(__name__)


async def on_startup():
    """Define FastAPI startup event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#startup-event

    """
    log.debug("Execute FastAPI startup event handler.")

    AiohttpClient.get_aiohttp_client()
    log.info(
        "persistence flags: %s",
        json.dumps(Container.flags().describe(["google"]), sort_keys=True),
    )
    await check_postgres_at_startup(Container.flags(), Container.pg_engine())


async def on_shutdown():
    """Define FastAPI shutdown event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#shutdown-event

    """
    log.debug("Execute FastAPI shutdown event handler.")
    # Gracefully close utilities.
    Container.executor = None
    await AiohttpClient.close_aiohttp_client()
    await dispose_engine(Container.pg_engine())


apm = make_apm_client()


def get_application():
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    log.debug("Initialize FastAPI application node.")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        version=settings.VERSION,
        docs_url=settings.API_ROOT_PATH + "/docs",
        openapi_url=settings.API_ROOT_PATH + "/openapi.json",
        on_startup=[on_startup, init_db],
        on_shutdown=[on_shutdown, close_db],
    )
    log.debug("Add application routes.")
    app.include_router(root_api_router)
    log.debug("Register global exception handler for custom HTTPException.")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(TimeoutError, timeout_error_handler)
    if settings.apm_settings.service_name and settings.apm_settings.server_url:
        app.add_middleware(ElasticAPM, client=apm)
    return app
