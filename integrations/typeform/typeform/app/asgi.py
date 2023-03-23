"""Application implementation - ASGI."""
import logging

from fastapi import FastAPI

from fastapi_utils.timing import add_timing_middleware

from loguru import logger

from typeform.app.container import container
from typeform.app.exceptions import HTTPException, http_exception_handler
from typeform.app.handlers import init_logging
from typeform.app.middlewares import include_middlewares
from typeform.app.router import root_api_router
from typeform.app.services.database_service import close_db, init_db
from typeform.config import settings

log = logging.getLogger(__name__)


async def on_startup():
    """Define FastAPI startup event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#startup-event

    """
    log.debug("Execute FastAPI startup event handler.")
    pass


async def on_shutdown():
    """Define FastAPI shutdown event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#shutdown-event

    """
    log.debug("Execute FastAPI shutdown event handler.")
    await container.http_client().aclose()
    # Gracefully close utilities.
    pass


def get_application():
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    init_logging()
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

    include_middlewares(app)
    add_timing_middleware(app, record=logger.info, prefix="app", exclude="untimed")

    return app
