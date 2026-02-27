"""Application implementation - ASGI."""

from contextlib import asynccontextmanager

from backend.config import settings
import common.exceptions.http
import sentry_sdk
from dependency_injector import providers
from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from fastapi_utils.timing import add_timing_middleware
from loguru import logger
from pymongo import AsyncMongoClient
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration

from backend.app.container import container
from backend.app.exceptions import HTTPException, http_exception_handler
from backend.app.handlers import init_logging
from backend.app.handlers.database import close_db, init_db
from backend.app.middlewares import DynamicCORSMiddleware, include_middlewares
from backend.app.router import root_api_router
from backend.app.utils import AiohttpClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager handling startup and shutdown."""
    # --- Startup ---
    logger.info("Execute FastAPI startup event handler.")

    AiohttpClient.get_aiohttp_client()

    # Use a pre-configured client (e.g. AsyncMongoMockClient injected by tests)
    # if one has already been set on the container; otherwise create a real one
    # inside the running event loop to avoid the
    # "AsyncMongoClient in different event loop" RuntimeError.
    client = container.database_client()
    if client is None:
        client = AsyncMongoClient(settings.mongo_settings.URI)
        container.database_client.override(providers.Object(client))
    await init_db(settings.mongo_settings.DB, client)

    yield

    # --- Shutdown ---
    logger.info("Execute FastAPI shutdown event handler.")

    await close_db(client)
    await AiohttpClient.close_aiohttp_client()
    await container.http_client().aclose()


def get_application(is_test_mode: bool = False):
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    init_logging()
    container.wire(packages=["backend.app"])
    logger.info("Initialize FastAPI application node.")
    api_settings = settings.api_settings
    sentry_settings = settings.sentry_settings
    if sentry_settings.DSN:
        sentry_sdk.init(
            dsn=sentry_settings.DSN,
            max_breadcrumbs=50,
            debug=sentry_settings.DEBUG,
            release=api_settings.VERSION,
            environment=api_settings.ENVIRONMENT,
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
        title=api_settings.TITLE,
        debug=settings.DEBUG,
        version=api_settings.VERSION,
        docs_url=api_settings.ROOT_PATH + "/docs",
        openapi_url=api_settings.ROOT_PATH + "/openapi.json",
        lifespan=lifespan,
    )

    logger.info("Add application routes.")
    app.include_router(root_api_router)
    app.add_middleware(
        DynamicCORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("Register global exception handler for custom HTTPException.")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(
        common.exceptions.http.HTTPException,
        common.exceptions.http.http_exception_handler,
    )

    logger.info("Register application middlewares.")
    include_middlewares(app)
    add_timing_middleware(app, record=logger.info, prefix="app", exclude="untimed")
    add_pagination(app)  # Important for paginating elements
    if settings.apm_settings.service_name and settings.apm_settings.server_url:
        apm = make_apm_client()
        app.add_middleware(ElasticAPM, client=apm)
    return app
