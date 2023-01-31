"""Application implementation - exceptions."""
from bettercollected_backend_server.app.exceptions.http import (
    HTTPException,
    http_exception_handler,
)


__all__ = ("HTTPException", "http_exception_handler")
