"""Application implementation - middlewares."""
from fastapi import FastAPI
from loguru import logger
from starlette.requests import Request
from starlette.responses import Response


__all__ = ("include_middlewares",)


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

        try:
            if hasattr(response, "body"):
                logger.info(f"Response: {response.status_code} {response.body}")
        except Exception as e:
            logger.error(f"Response Error: {e}")
            return response
        return response
