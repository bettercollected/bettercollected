"""Application implementation - Ready controller."""
import logging

from fastapi import APIRouter
from auth.config import settings
from auth.app.views import ReadyResponse


router = APIRouter()
log = logging.getLogger(__name__)


@router.get(
    "/ready",
    tags=["ready"],
    response_model=ReadyResponse,
    summary="Simple health check.",
    status_code=200,
)
async def readiness_check():
    """Run basic application health check.

    If the application is up and running then this endpoint will return simple
    response with status ok. Moreover, if it has Redis enabled then connection
    to it will be tested. If Redis ping fails, then this endpoint will return
    502 HTTP error.
    \f

    Returns:
        response (ReadyResponse): ReadyResponse model object instance.

    Raises:
        HTTPException: If applications has enabled Redis and can not connect
            to it. NOTE! This is the custom exception, not to be mistaken with
            FastAPI.HTTPException class.

    """
    log.info("Started GET /ready")

    if settings.USE_REDIS:
        log.warning(
            "Redis utility skipped. Please set FASTAPI_USE_REDIS=false"
        )

    return ReadyResponse(status="ok")
