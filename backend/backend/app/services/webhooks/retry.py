"""The delivery job's retry schedule: 6 attempts in all, with exponential
backoff (30 seconds, then x4 each time: 30 s, 2 min, 8 min, 32 min, about
2 hours, capped at 6 hours) and +-25% jitter so a destination that comes back
is not hit by every waiting delivery at the same second. A longer
``Retry-After`` of the destination wins (capped by the client). After the last
attempt the delivery is ``failed`` and visible in the log."""

import random
from typing import Callable, Optional

from procrastinate import BaseRetryStrategy
from procrastinate.retry import RetryDecision

MAX_ATTEMPTS = 6
BASE_SECONDS = 30
FACTOR = 4
CAP_SECONDS = 6 * 3600
JITTER = 0.25


def backoff_seconds(
    attempt_index: int, rand: Callable[[], float] = random.random
) -> int:
    """The wait after attempt ``attempt_index`` (0 for the first) failed."""
    base = min(CAP_SECONDS, BASE_SECONDS * FACTOR ** max(0, attempt_index))
    spread = base * JITTER
    return max(1, int(round(base + (rand() * 2 - 1) * spread)))


class WebhookRetry(Exception):
    """Raised by the job so procrastinate retries it (never carries content)."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__("retry")
        self.retry_after = retry_after


class WebhookRetryStrategy(BaseRetryStrategy):
    def __init__(self, rand: Callable[[], float] = random.random):
        self._rand = rand

    def get_retry_decision(self, *, exception, job):
        if job.attempts + 1 >= MAX_ATTEMPTS:
            return None
        wait = backoff_seconds(job.attempts, self._rand)
        after = getattr(exception, "retry_after", None) or 0
        return RetryDecision(retry_in={"seconds": max(wait, after)})
