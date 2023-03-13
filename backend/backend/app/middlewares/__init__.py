"""Application implementation - middlewares."""
from fastapi import FastAPI
from loguru import logger
from starlette.requests import Request
from starlette.responses import Response

__all__ = ("include_middlewares",)

from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware


def include_middlewares(app: "FastAPI"):
    """
    Include middlewares in the given FastAPI app.

    Parameters:
        app: A FastAPI app instance.
    """

    @app.middleware("http")
    async def request_logger(request: "Request", call_next):
        """
        Middleware for logging requests and responses for debugging purposes.

        Logs the client IP, request method, URL, and query parameters.
        If in development mode, also logs the response status code and body.

        Raises:
            Exception: If there is an error while logging the response.
        """
        logger.info(f'Client Ip : {request.headers.get("X-Forwarded-For")}')
        logger.info(
            f"Request : Host {request.method} {request.url.path} {request.url.query}"
        )
        response: Response = await call_next(request)
        logger.info(response.status_code)
        return response
