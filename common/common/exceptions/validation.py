"""Request validation errors without the submitted values.

FastAPI's default 422 body echoes each failing value (``input``) and the
validator context (``ctx``), so a rejected password, token or form answer is
sent straight back (and into any proxy or client log). This handler keeps the
shape clients rely on, a ``detail`` list of ``loc`` / ``msg`` / ``type``, and
drops the rest.

A custom validator that raises ``ValueError(f"... {value} ...")`` puts the
submitted value into ``msg`` itself. The handler removes every string of the
failing input from the message (``echo_free``), so a validator author cannot
reintroduce the echo by accident. Only whole tokens are removed: a submitted
value that merely occurs inside a longer word of the message ("mat" in
"format") leaves that word alone.
"""
import re
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


def _whole(leaf: str) -> "re.Pattern[str]":
    """``leaf`` where it is not part of a longer word: no letter, digit or
    underscore directly before or after it."""
    return re.compile(r"(?<!\w)" + re.escape(leaf) + r"(?!\w)")


def echo_free(message: str, submitted: Any) -> str:
    """``message`` with every string of ``submitted`` replaced by an ellipsis:
    inside quotes for any string, and as a whole token (not inside a longer
    word) for strings of three or more characters, so ordinary words in the
    message are not mangled."""
    leaves = sorted(set(_strings(submitted)), key=len, reverse=True)
    for leaf in leaves:
        for quote in ("'", '"'):
            message = message.replace(f"{quote}{leaf}{quote}", f"{quote}{ELLIPSIS}{quote}")
        if len(leaf) >= MIN_PLAIN:
            message = _whole(leaf).sub(ELLIPSIS, message)
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
