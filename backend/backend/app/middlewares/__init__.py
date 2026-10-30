"""Application implementation - middlewares."""
from http import HTTPStatus
from traceback import print_exception
from fastapi import FastAPI

from loguru import logger

from starlette.requests import Request
from starlette.responses import Response

__all__ = ("include_middlewares",)

from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware
from backend.app.middlewares.request_privacy import (
    NO_STORE_HEADERS,
    carries_response_data,
    loggable_request,
)


def include_middlewares(app: "FastAPI"):
    """
    Include middlewares in the given FastAPI app.

    Parameters:
        app: A FastAPI app instance.
    """

    @app.middleware("http")
    async def base_exception_handler(request: "Request", call_next):
        try:
            return await call_next(request)
        except Exception as e:
            print_exception(e)
            return Response("Internal server error", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


    @app.middleware("http")
    async def request_logger(request: "Request", call_next):
        """
        Middleware for logging requests and responses for debugging purposes.

        Logs the method, the path with any receipt number redacted, and the
        status code. Never the query string (the responses search sends a
        respondent's email there), never the client's address
        (X-Forwarded-For).
        """
        logger.info("Request : {}", loggable_request(request.method, request.url.path))
        response: Response = await call_next(request)
        logger.info(response.status_code)
        return response

    @app.middleware("http")
    async def no_store_response_data(request: "Request", call_next):
        """Decrypted answers are never kept by a browser or proxy cache: on a
        shared computer they would outlive the session and come back on
        back/forward."""
        response: Response = await call_next(request)
        if carries_response_data(request.url.path):
            for name, value in NO_STORE_HEADERS.items():
                response.headers[name] = value
        return response
