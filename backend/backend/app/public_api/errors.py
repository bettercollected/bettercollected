"""One error shape for the whole public API:
``{"code", "message", "errors"?: [{"path", "message"}]}``.

``path`` is a JSON pointer into the request body ("" for the body as a
whole); ``code`` is stable and meant for programs, ``message`` for people.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional

import common.exceptions.http
from common.exceptions import NotFoundError
from common.form_spec.adapters import json_path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.exceptions import HTTPException

DEFAULT_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    412: "precondition_failed",
    413: "payload_too_large",
    422: "unprocessable",
    428: "precondition_required",
    429: "rate_limited",
}


def _default_message(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def error_payload(status: int, content: Any) -> Dict[str, Any]:
    """The API's error body for a status and an exception's content (a
    string, or a dict with ``code``/``message``/``errors``)."""
    code: Optional[str] = None
    message: Optional[str] = None
    errors: Optional[List[Any]] = None
    if isinstance(content, dict):
        code = content.get("code")
        message = (
            content.get("message") or content.get("error") or content.get("detail")
        )
        errors = content.get("errors")
    elif content is not None:
        message = str(content)
    payload: Dict[str, Any] = {
        "code": str(
            code
            or DEFAULT_CODES.get(status)
            or ("internal_error" if status >= 500 else "error")
        ),
        "message": str(message or _default_message(status)),
    }
    if errors:
        payload["errors"] = [
            {
                "path": str(e.get("path") or "") if isinstance(e, dict) else "",
                "message": (
                    str(e.get("message") or "") if isinstance(e, dict) else str(e)
                ),
            }
            for e in errors
        ]
    return payload


def error_response(
    status: int, content: Any, headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=error_payload(status, content), headers=headers
    )


def install_error_handlers(app: FastAPI) -> None:
    async def http_error(request: Request, error: HTTPException):
        return error_response(error.status_code, error.content, error.headers)

    async def starlette_error(request: Request, error: StarletteHTTPException):
        return error_response(error.status_code, error.detail, error.headers)

    async def validation_error(request: Request, error: RequestValidationError):
        errors = []
        for e in error.errors():
            loc = list(e.get("loc") or ())
            where = loc[0] if loc else None
            path = json_path(loc[1:]) if where == "body" else ""
            name = ".".join(str(p) for p in loc[1:]) if where != "body" else ""
            message = str(e.get("msg") or "")
            errors.append(
                {"path": path, "message": f"{name}: {message}" if name else message}
            )
        return error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {
                "code": "invalid_request",
                "message": "The request is not valid.",
                "errors": errors,
            },
        )

    async def not_found(request: Request, error: NotFoundError):
        return error_response(HTTPStatus.NOT_FOUND, "Not found")

    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(common.exceptions.http.HTTPException, http_error)
    app.add_exception_handler(StarletteHTTPException, starlette_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(NotFoundError, not_found)
