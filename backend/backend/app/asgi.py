"""Application implementation - ASGI."""

import asyncio
from contextlib import asynccontextmanager

from backend.config import settings
import common.exceptions.http
from common.exceptions.validation import request_validation_error_handler
from common.services.crypto_service import crypto_service
from fastapi.exceptions import RequestValidationError
from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from fastapi_utils.timing import add_timing_middleware
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException, http_exception_handler
from backend.app.handlers import init_logging
from backend.db.startup import check_postgres_at_startup, dispose_postgres
from backend.jobs.app import app as jobs_app, postgres_jobs_enabled
from backend.app.mcp.server import build_mcp_asgi_app, mcp
from backend.app.middlewares import DynamicCORSMiddleware, include_middlewares
from backend.app.public_api.app import PUBLIC_API_PATH, build_public_api_asgi
from backend.app.router import root_api_router
from backend.app.services.internal_auth import log_if_internal_key_missing
from backend.app.services.custom_domain_origins import prune_unverified_origins
from backend.app.services.internal_job_key import log_if_job_api_key_missing
from backend.app.services.sso.startup import log_if_sso_incomplete
from backend.app.services.umami_client import provision_umami_website
from backend.app.utils import AiohttpClient
from backend.app.utils.respondent_identity import (
    IdentityKeyError,
    identity_key_unavailable,
    require_identity_key,
)
from backend.identity_rekey import check_key_at_startup, start_background_passes
from scripts.seed_flow_templates import seed_flow_templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager handling startup and shutdown."""
    # --- Startup ---
    logger.info("Execute FastAPI startup event handler.")
    # The respondent identity hash is keyed: never serve without its key (a
    # missing one would silently store and match unusable identities).
    require_identity_key("the backend", settings.respondent_identity.KEY)
    log_if_internal_key_missing()
    log_if_job_api_key_missing()
    log_if_sso_incomplete()
    # the response keyset (environment or settings store): fail at startup, not on the first response read
    crypto_service.load()

    AiohttpClient.get_aiohttp_client()

    await check_postgres_at_startup(container)
    # A key that is not the one that converted the stored identities stops the
    # start here; the conversion itself runs in the background below, once the
    # API serves (matching refuses a non-v2 value meanwhile).
    await check_key_at_startup(container.pg_engine())
    jobs_on_postgres = postgres_jobs_enabled(container.flags())
    if jobs_on_postgres:
        await jobs_app.open_async()

    # Auto-provision the Umami website (find-or-create by UMAMI_WEBSITE_NAME)
    # when UMAMI_WEBSITE_ID isn't already set — lets self-hosters skip creating
    # a website by hand in the Umami UI. No-op without UMAMI_URL/USERNAME/
    # PASSWORD; never blocks startup on failure (Umami may not be up yet on a
    # fresh deploy — analytics endpoints just stay unavailable until it is and
    # the backend is restarted). See backend/AGENTS.md "Analytics (Umami)".
    if (
        settings.umami_settings.has_credentials
        and not settings.umami_settings.WEBSITE_ID
    ):
        try:
            settings.umami_settings.WEBSITE_ID = await provision_umami_website()
            logger.info(
                f"Umami website resolved: {settings.umami_settings.WEBSITE_ID} "
                f"(name={settings.umami_settings.WEBSITE_NAME!r})"
            )
        except Exception:
            logger.exception(
                "Umami website auto-provisioning failed; continuing startup."
            )

    # Auto-seed the flow-native template gallery (idempotent — skips templates
    # that already exist). Gated by DEFAULT_SEED_FLOW_TEMPLATES (default on) and
    # a no-op without DEFAULT_WORKSPACE_ID. Never blocks startup on failure —
    # see backend/AGENTS.md "Seed scripts" for the full writeup.
    if settings.default_workspace_settings.SEED_FLOW_TEMPLATES:
        workspace_id = settings.default_workspace_settings.WORKSPACE_ID
        if not workspace_id:
            logger.warning(
                "DEFAULT_WORKSPACE_ID is not set — skipping flow-template gallery seeding."
            )
        else:
            try:
                result = await seed_flow_templates(
                    workspace_id, template_repo=container.form_template_repo()
                )
                if result["seeded"]:
                    logger.info(f"Seeded flow templates: {', '.join(result['seeded'])}")
                if result["repaired"]:
                    logger.info(
                        f"Repaired yes/no choices in flow templates: {', '.join(result['repaired'])}"
                    )
                if result["restyled"]:
                    logger.info(
                        f"Moved flow templates to Leaflet: {', '.join(result['restyled'])}"
                    )
            except Exception:
                logger.exception("Flow-template seeding failed; continuing startup.")

    # Only verified custom domains are allowed origins; bring the stored origins
    # in line with that on every boot (idempotent, never blocks startup).
    try:
        pruned = await prune_unverified_origins(
            container.allowed_origins_repo(), container.workspace_repo()
        )
        if pruned["removed"]:
            logger.info(
                f"Removed {len(pruned['removed'])} allowed origins of unverified "
                "custom domains"
            )
        if pruned["orphans"]:
            logger.warning(
                f"{len(pruned['orphans'])} allowed origins match no workspace; review "
                "them with `python -m backend.custom_domain prune-origins --dry-run`"
            )
    except Exception:
        logger.exception("Pruning allowed origins failed; continuing startup.")

    # The MCP session manager must be running for the mounted /mcp app to
    # serve requests (streamable-HTTP transport requirement). It runs in its
    # own task: anyio task groups must be entered and exited in the same task,
    # and lifespan setup/teardown are not guaranteed to share one (they don't
    # under pytest-asyncio).
    mcp_started, mcp_stop = asyncio.Event(), asyncio.Event()

    async def _run_mcp_session_manager():
        async with mcp.session_manager.run():
            mcp_started.set()
            await mcp_stop.wait()

    mcp_task = asyncio.create_task(_run_mcp_session_manager())
    await mcp_started.wait()

    # Convert any stored identity that is not v2 yet, in the background: idempotent,
    # one replica at a time, counts only, once more a few minutes later for a 4.0
    # replica still writing (docs/respondent-identity.md). Never stops the API.
    identity_task = start_background_passes(container.pg_engine())

    yield

    # --- Shutdown ---
    logger.info("Execute FastAPI shutdown event handler.")

    if identity_task is not None:
        identity_task.cancel()
        try:
            await identity_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 — never skips the rest of the shutdown
            logger.warning("respondent identity task ended with {}", type(exc).__name__)

    mcp_stop.set()
    await mcp_task
    # Sheets reconnect mails in flight: finished or released while the
    # stores are still open (services/sheets_reconsent.py)
    try:
        await container.sheets_reconsent_service().shutdown()
    except Exception as exc:  # noqa: BLE001 — never blocks the shutdown
        logger.warning("sheets reconsent shutdown failed ({})", type(exc).__name__)
    if jobs_on_postgres:
        await jobs_app.close_async()
    await dispose_postgres(container)
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
    app = FastAPI(
        title=api_settings.TITLE,
        debug=settings.DEBUG,
        version=api_settings.VERSION,
        docs_url=api_settings.ROOT_PATH + "/docs" if api_settings.DOCS_ENABLED else None,
        redoc_url=api_settings.ROOT_PATH + "/redoc" if api_settings.DOCS_ENABLED else None,
        openapi_url=api_settings.ROOT_PATH + "/openapi.json" if api_settings.DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    logger.info("Add application routes.")
    app.include_router(root_api_router)
    # MCP endpoint — other LLMs drive BetterCollected through this (plan §2.5).
    # Auth: workspace API keys as Bearer tokens, enforced by the wrapping
    # middleware; the session manager lifecycle is handled in lifespan above.
    app.mount(api_settings.ROOT_PATH + "/mcp", build_mcp_asgi_app())
    # Public REST API — forms as code (docs/api/README.md). Its own app: its
    # own OpenAPI document and error shape, Bearer API keys only.
    app.mount(api_settings.ROOT_PATH + PUBLIC_API_PATH, build_public_api_asgi())
    app.add_middleware(
        DynamicCORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # the Open Formulieren export: its file name and how many things it
        # could not carry over (read by the webapp across origins)
        expose_headers=["Content-Disposition", "X-Open-Formulieren-Unmapped"],
    )
    logger.info("Register global exception handler for custom HTTPException.")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(IdentityKeyError, identity_key_unavailable)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
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
    # verified domains are SSO trust grants: name what a hosted stack misses
    for warning in settings.verified_domains.warnings(settings.sso.is_configured):
        logger.warning(warning)
    return app
