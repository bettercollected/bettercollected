"""Application implementation - ASGI."""
import logging

import auth
from auth.app.container import container
from auth.app.exceptions import (
    HTTPException,
    http_exception_handler,
)
from auth.app.router import root_api_router
from auth.app.services.database_service import close_db, init_db
from auth.config import settings

from fastapi import FastAPI

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


def get_application():
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    log.debug("Initialize FastAPI application node.")
    container.wire(packages=[auth.app])
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
    return app
