from fastapi import FastAPI
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


def init_exception_handlers(app: "FastAPI"):
    """
    Initializes exception handlers for the specified FastAPI app.

    This function defines an exception handler for HTTPException instances,
    which logs the request and exception detail and returns a JSONResponse
    with the exception's status code and detail as the content.

    Parameters:
    app (FastAPI): The FastAPI app instance to initialize exception handlers for.

    Returns:
    None
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        """
        Handles `HTTPException` instances and returns a `JSONResponse` with the
        exception's status code and detail as the content.

        This function logs the request and exception detail, and returns a
        `JSONResponse` with the exception's status code and detail as the content.

        Parameters:
            request (Request): The incoming request object.
            exc (HTTPException): The exception to handle.

        Returns:
            JSONResponse: A response with the exception's status code and detail as the content.
        """
        logger.info(request)
        logger.error(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
