"""A fixed-window request limiter shared by every replica.

Each (scope, client, window) gets one counter in the database
(``rate_limit_counters``), incremented atomically. Its id is a keyed hash of
those three, so no counter names a client: the key is derived from a server
secret, and without it the id can't be matched against candidate addresses.
"""

import datetime as dt
import hashlib
import hmac
import math
import time
from dataclasses import dataclass
from typing import Callable

from backend.app.repositories.rate_limit_repository import RateLimitRepository

_KEY_LABEL = b"bettercollected rate-limit counter v1\0"


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    count: int
    retry_after: int  # seconds until the window ends


class FixedWindowRateLimiter:
    def __init__(
        self,
        repo: RateLimitRepository,
        secret: str,
        clock: Callable[[], float] = time.time,
    ):
        self._repo = repo
        self._key = hashlib.sha256(_KEY_LABEL + (secret or "").encode()).digest()
        self._clock = clock

    def counter_id(self, scope: str, client: str, window: int) -> str:
        message = f"{scope}\n{client}\n{window}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()[:24]

    async def hit(
        self, scope: str, client: str, limit: int, window_seconds: int
    ) -> Verdict:
        """Count one request of ``client`` in ``scope``; allowed while the
        window's count is at most ``limit``."""
        window_seconds = max(1, int(window_seconds))
        now = self._clock()
        window = int(now // window_seconds)
        ends = (window + 1) * window_seconds
        count = await self._repo.hit(
            self.counter_id(scope, client, window),
            dt.datetime.fromtimestamp(ends + window_seconds, dt.timezone.utc),
        )
        return Verdict(
            allowed=count <= limit,
            count=count,
            retry_after=max(1, math.ceil(ends - now)),
        )
