"""Request validation errors without the submitted values.

FastAPI's default 422 body echoes each failing value (``input``) and the
validator context (``ctx``), so a rejected password, token or form answer is
sent straight back (and into any proxy or client log). This handler keeps the
shape clients rely on, a ``detail`` list of ``loc`` / ``msg`` / ``type``, and
drops the rest.

A custom validator that raises ``ValueError(f"... {value} ...")`` puts the
submitted value into ``msg`` itself. The handler removes every string of the
failing input from the message (``echo_free``), so a validator author cannot
reintroduce the echo by accident.
"""
from http import HTTPStatus
from typing import Any, List, Optional

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ELLIPSIS = "…"
MIN_PLAIN = 3  # shorter strings are only removed when quoted ('a', "a")
MAX_LEAVES = 200
MAX_DEPTH = 4


def _strings(value: Any, depth: int = 0, found: Optional[List[str]] = None) -> List[str]:
    """The string leaves of an input (a str, or strings inside lists, tuples and
    dicts), bounded in count and depth."""
    found = [] if found is None else found
    if len(found) >= MAX_LEAVES or depth > MAX_DEPTH:
        return found
    if isinstance(value, str):
        if value:
            found.append(value)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _strings(item, depth + 1, found)
    elif isinstance(value, dict):
        for key, item in value.items():
            _strings(key, depth + 1, found)
            _strings(item, depth + 1, found)
    return found


def echo_free(message: str, submitted: Any) -> str:
    """``message`` with every string of ``submitted`` replaced by an ellipsis:
    anywhere for strings of three or more characters, and inside quotes for
    shorter ones (so ordinary words in the message are not mangled)."""
    leaves = sorted(set(_strings(submitted)), key=len, reverse=True)
    for leaf in leaves:
        for quote in ("'", '"'):
            message = message.replace(f"{quote}{leaf}{quote}", f"{quote}{ELLIPSIS}{quote}")
        if len(leaf) >= MIN_PLAIN:
            message = message.replace(leaf, ELLIPSIS)
    return message


async def request_validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    detail = [
        {
            "loc": list(item.get("loc") or ()),
            "msg": echo_free(str(item.get("msg") or ""), item.get("input")),
            "type": str(item.get("type") or ""),
        }
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": detail}),
    )
