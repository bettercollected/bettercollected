"""A work budget for one import: characters of text processed and wall-clock
time. The archive is untrusted, so what a build may spend is bounded whatever
it holds; a build over budget is refused as too complex (422), never left to
run. The budget is per build and reached through a context variable, so the
text helpers need no extra argument."""

from __future__ import annotations

import contextlib
import time
from contextvars import ContextVar
from http import HTTPStatus
from typing import Iterator, Optional

from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.errors import refuse


class Budget:
    def __init__(self, max_chars: int, seconds: float) -> None:
        self.max_chars = max_chars
        self.spent = 0
        self.deadline = time.monotonic() + seconds

    def _over(self) -> None:
        raise refuse(
            "archive_too_complex",
            "The form is too large or too slow to import.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    def charge(self, chars: int) -> None:
        self.spent += chars
        if self.spent > self.max_chars:
            self._over()
        self.check()

    def check(self) -> None:
        if time.monotonic() > self.deadline:
            self._over()


_CURRENT: ContextVar[Optional[Budget]] = ContextVar("open_formulieren_budget", default=None)


@contextlib.contextmanager
def scope() -> Iterator[Budget]:
    """The budget of the running build: the enclosing one when there is one
    (so decoding and building share it), else a new one."""
    existing = _CURRENT.get()
    if existing is not None:
        yield existing
        return
    budget = Budget(limits.MAX_TEXT_CHARS, limits.BUILD_SECONDS)
    token = _CURRENT.set(budget)
    try:
        yield budget
    finally:
        _CURRENT.reset(token)


def charge(chars: int) -> None:
    budget = _CURRENT.get()
    if budget is not None:
        budget.charge(chars)


def check() -> None:
    budget = _CURRENT.get()
    if budget is not None:
        budget.check()
