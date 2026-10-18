"""Time source for the security primitives.

Everything that depends on the current time takes a ``Clock`` so tests move
time by hand instead of sleeping.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def time(self) -> float:
        """Seconds since the Unix epoch."""
        ...

    def now(self) -> datetime:
        """The current moment as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """The real clock."""

    def time(self) -> float:
        return time.time()

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """A clock that only moves when told to; for tests."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self._now = float(start)

    def time(self) -> float:
        return self._now

    def now(self) -> datetime:
        return datetime.fromtimestamp(self._now, timezone.utc)

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def advance_delta(self, delta: timedelta) -> None:
        self._now += delta.total_seconds()

    def set(self, timestamp: float) -> None:
        self._now = float(timestamp)
