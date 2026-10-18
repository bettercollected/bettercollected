"""Request validation errors without the submitted values.

FastAPI's default 422 body echoes each failing value (``input``) and the
validator context (``ctx``), so a rejected password, token or form answer is
sent straight back (and into any proxy or client log). This handler keeps the
shape clients rely on, a ``detail`` list of ``loc`` / ``msg`` / ``type``, and
drops the rest.
"""
from http import HTTPStatus

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def request_validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    detail = [
        {
            "loc": list(item.get("loc") or ()),
            "msg": str(item.get("msg") or ""),
            "type": str(item.get("type") or ""),
        }
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": detail}),
    )
