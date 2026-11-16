"""How deeply a JSON request body may nest, checked before anything parses it.

``json.loads`` recurses once per level, and on CPython 3.11 it gives up with a
``RecursionError`` a little under a thousand levels, the exact number depending
on how many frames the request already uses. A body that deep is a few KB of
brackets, so anybody can send one; left alone it turned into a server error.
Everything that reads a JSON body now refuses one nested deeper than
``MAX_JSON_DEPTH`` first, with the answer ``body_too_deep``.

The limit: the deepest document a client legitimately sends is a form with a
rich-text title (nested at most 64 levels, ``TITLE_JSON_MAX_DEPTH``) inside a
question inside a page inside the form, or an expression (at most 32 levels,
two brackets each) inside a rule inside a question, inside an operations
request: about 70 brackets at worst. 128 leaves about 55 levels of room above
that and is about 7 times below where the parser fails, so a refusal never
depends on how deep the stack already is.

``MAX_JSON_DEPTH`` is mirrored by the Rust edge (``rust/bc-crypto``): change
both together.
"""

import json
import re
from http import HTTPStatus
from typing import Any, Union

from backend.app.exceptions import HTTPException

MAX_JSON_DEPTH = 128

CODE = "body_too_deep"
MESSAGE = f"The request body is nested too deeply (at most {MAX_JSON_DEPTH} levels)."

# One token at a time, never backtracking into a string: a whole string
# (escapes honoured, a closing quote or the end of the input ends it), or a
# bracket. Quotes and brackets inside a string belong to the string.
_TOKEN_BYTES = re.compile(rb'"[^"\\]*+(?:\\.[^"\\]*+)*+(?:"|\\?\Z)|[\[\]{}]', re.DOTALL)
_TOKEN_TEXT = re.compile(r'"[^"\\]*+(?:\\.[^"\\]*+)*+(?:"|\\?\Z)|[\[\]{}]', re.DOTALL)
_BYTES = (_TOKEN_BYTES, (b"[", b"{"), (b"]", b"}"))
_TEXT = (_TOKEN_TEXT, ("[", "{"), ("]", "}"))


def too_deep(raw: Union[bytes, bytearray, str], limit: int = MAX_JSON_DEPTH) -> bool:
    """Whether ``raw`` nests arrays and objects deeper than ``limit``.

    Iterative and linear, never copies ``raw``, and does not need the input to
    be valid JSON (anything that is not nests no deeper than it counts: the
    parser refuses it on its own). A string that never ends swallows the rest
    of the input.
    """
    pattern, openers, closers = _TEXT if isinstance(raw, str) else _BYTES
    # every level takes an opening bracket: fewer of those cannot be too deep
    if sum(raw.count(opener) for opener in openers) <= limit:
        return False
    depth = 0
    for match in pattern.finditer(raw):
        token = match.group()
        if token in openers:
            depth += 1
            if depth > limit:
                return True
        elif token in closers:
            # never below zero: stray closers do not buy extra levels
            depth = depth - 1 if depth else 0
    return False


def body_too_deep() -> HTTPException:
    """The refusal, 422 like the other answers to a body that cannot be
    parsed (``{"code", "message"}``, which both error shapes of the API
    carry)."""
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": CODE, "message": MESSAGE},
    )


def loads(raw: Union[bytes, bytearray, str]) -> Any:
    """``json.loads`` for a body from outside: ``body_too_deep`` (422) for one
    nested beyond ``MAX_JSON_DEPTH`` (checked before the parser starts), and
    again for the ``RecursionError`` a parser nested deeper than the stack
    allows would raise anyway. Other problems stay a ``ValueError``."""
    if isinstance(raw, (str, bytes, bytearray)) and too_deep(raw):
        raise body_too_deep()
    try:
        return json.loads(raw)
    except RecursionError:
        raise body_too_deep()
