"""Request validation errors without the submitted values.

FastAPI's default 422 body echoes each failing value (``input``) and the
validator context (``ctx``), so a rejected password, token or form answer is
sent straight back (and into any proxy or client log). This handler keeps the
shape clients rely on, a ``detail`` list of ``loc`` / ``msg`` / ``type``, and
drops the rest.

A custom validator that raises ``ValueError(f"... {value} ...")`` puts the
submitted value into ``msg`` itself. The handler removes every string of the
failing input from the message (``echo_free``), so a validator author cannot
reintroduce the echo by accident. A short value (3 to 7 characters) is removed
as a whole token only, so it does not mangle ordinary words ("mat" in "format");
a longer one is removed wherever it occurs, because a value that long does not
appear inside an ordinary word by accident, and a validator that glues it to
other text ("user_{value}") must not echo it.
"""
from http import HTTPStatus
from typing import Any, List, Optional

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ELLIPSIS = "…"
MIN_PLAIN = 3  # shorter strings are only removed when quoted ('a', "a")
MIN_ANYWHERE = 8  # from this length on a string is removed wherever it occurs
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


def _word(char: str) -> bool:
    """A letter, digit or underscore (what ``\\w`` matches)."""
    return char.isalnum() or char == "_"


def _scrub_whole(message: str, leaf: str) -> str:
    """``message`` with ``leaf`` replaced where it is not part of a longer word:
    no letter, digit or underscore directly before it (when its own first
    character is one) or after it (likewise its last). Plain ``str.find`` and
    index checks, so the cost is linear and nothing is compiled from input."""
    size = len(leaf)
    check_before, check_after = _word(leaf[0]), _word(leaf[-1])
    out: List[str] = []
    at = 0
    while True:
        found = message.find(leaf, at)
        if found < 0:
            break
        end = found + size
        if (not check_before or found == 0 or not _word(message[found - 1])) and (
            not check_after or end >= len(message) or not _word(message[end])
        ):
            out.append(message[at:found])
            out.append(ELLIPSIS)
            at = end
        else:
            out.append(message[at : found + 1])
            at = found + 1
    out.append(message[at:])
    return "".join(out)


def echo_free(message: str, submitted: Any) -> str:
    """``message`` with every string of ``submitted`` replaced by an ellipsis:
    inside quotes for any string; as a whole token (not inside a longer word)
    for strings of 3 to 7 characters, so ordinary words in the message are not
    mangled; anywhere for strings of 8 or more. A string longer than the message
    cannot occur in it and is skipped."""
    leaves = sorted(set(_strings(submitted)), key=len, reverse=True)
    for leaf in leaves:
        if len(leaf) > len(message):
            continue
        for quote in ("'", '"'):
            message = message.replace(f"{quote}{leaf}{quote}", f"{quote}{ELLIPSIS}{quote}")
        if len(leaf) >= MIN_ANYWHERE:
            message = message.replace(leaf, ELLIPSIS)
        elif len(leaf) >= MIN_PLAIN:
            message = _scrub_whole(message, leaf)
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
