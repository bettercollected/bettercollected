"""One clock reading per routed write.

A mirrored write that is re-executed on the mirror store (the default for
``@write_op`` methods) only produces the same document there when the call is
deterministic in its arguments. The current time is the one input both
implementations read for themselves: ``created_at`` and ``updated_at`` stamps,
counters' windows, ``last_logged_in``. Read separately, the two stores end up
a few milliseconds apart and ``verify`` reports every such document as
mismatched.

:class:`common.db.routing.RoutingRepository` therefore opens a
:func:`write_clock` around the primary write and its mirror, and the code
paths that stamp documents read :func:`utcnow`: within a routed write it is
the same instant for both stores, outside one it is simply the current time.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Iterator, Optional

_write_now: ContextVar[Optional[datetime]] = ContextVar("bc_write_now", default=None)


def utcnow() -> datetime:
    """The current time (aware UTC), fixed for the duration of a routed write."""
    fixed = _write_now.get()
    return fixed if fixed is not None else datetime.now(timezone.utc)


@contextmanager
def write_clock() -> Iterator[datetime]:
    """Fix :func:`utcnow` for the enclosed block. Nested blocks (a routed
    write calling another) share the outermost reading."""
    current = _write_now.get()
    if current is not None:
        yield current
        return
    token = _write_now.set(datetime.now(timezone.utc))
    try:
        yield _write_now.get()
    finally:
        _write_now.reset(token)
