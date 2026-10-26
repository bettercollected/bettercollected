"""Application implementation - ASGI."""

import json
import logging

import auth
import sentry_sdk
from auth.app.container import container
from auth.app.controllers.internal_key import log_if_internal_key_missing
from auth.app.exceptions import (
    HTTPException,
    http_exception_handler,
)
from auth.app.exceptions.http import not_found_error_handler
from auth.app.router import root_api_router
from auth.db.base import SCHEMA
from common.db import MigrationTarget, check_postgres_at_startup, dispose_engine
from auth.config import settings
from elasticapm.contrib.starlette import make_apm_client, ElasticAPM
from fastapi import FastAPI
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration

from common.exceptions import NotFoundError
from common.settings import sso_requirements
from common.exceptions.validation import request_validation_error_handler
from fastapi.exceptions import RequestValidationError

log = logging.getLogger(__name__)

# The auth schema's Alembic history: checked (and with DB_AUTO_MIGRATE=true,
# applied) at startup.
MIGRATIONS = MigrationTarget.for_package(auth, SCHEMA, service="auth")


def log_if_sso_incomplete() -> bool:
    """Log a warning at startup when SSO_ENABLED is true but a setting single
    sign-on needs is missing (names only). True when nothing is missing."""
    sso = settings.sso_settings
    if not sso.ENABLED:
        return True
    missing = sso.missing_settings
    if not missing:
        return True
    log.warning("%s", sso_requirements.startup_message("auth", missing))
    return False


async def on_startup():
    """Define FastAPI startup event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#startup-event

    """
    log.debug("Execute FastAPI startup event handler.")
    log_if_internal_key_missing()
    log_if_sso_incomplete()
    flags = container.flags()  # refuses a stale DB_* flag (auth/db/flags.py)
    log.info("persistence flags: %s", json.dumps(flags.describe(), sort_keys=True))
    if container.pg_engine() is None:
        raise RuntimeError(
            "DATABASE_URL is not set: the auth service stores its data in "
            "Postgres only since 4.1"
        )
    await check_postgres_at_startup(flags, container.pg_engine(), MIGRATIONS)


async def on_shutdown():
    """Define FastAPI shutdown event handler.

    Resources:
        1. https://fastapi.tiangolo.com/advanced/events/#shutdown-event

    """
    log.debug("Execute FastAPI shutdown event handler.")
    await container.http_client().aclose()
    await dispose_engine(container.pg_engine())


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
        docs_url=settings.API_ROOT_PATH + "/docs" if settings.API_DOCS_ENABLED else None,
        redoc_url=settings.API_ROOT_PATH + "/redoc" if settings.API_DOCS_ENABLED else None,
        openapi_url=settings.API_ROOT_PATH + "/openapi.json" if settings.API_DOCS_ENABLED else None,
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )
    log.debug("Add application routes.")
    app.include_router(root_api_router)
    log.debug("Register global exception handler for custom HTTPException.")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(NotFoundError, not_found_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    if settings.apm_settings.service_name and settings.apm_settings.server_url:
        app.add_middleware(ElasticAPM, client=apm)
    return app
