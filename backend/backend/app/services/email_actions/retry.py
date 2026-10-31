"""The delivery job's retry schedule: 5 attempts in all, with exponential
backoff (1 minute, then x4 each time: 1, 4, 16 and 64 minutes, capped at 2
hours) and +-25% jitter. After the last attempt the delivery is ``failed`` and
visible in the log."""

import random
from typing import Callable, Optional

from procrastinate import BaseRetryStrategy
from procrastinate.retry import RetryDecision

MAX_ATTEMPTS = 5
BASE_SECONDS = 60
FACTOR = 4
CAP_SECONDS = 2 * 3600
JITTER = 0.25


def backoff_seconds(
    attempt_index: int, rand: Callable[[], float] = random.random
) -> int:
    """The wait after attempt ``attempt_index`` (0 for the first) failed."""
    base = min(CAP_SECONDS, BASE_SECONDS * FACTOR ** max(0, attempt_index))
    spread = base * JITTER
    return max(1, int(round(base + (rand() * 2 - 1) * spread)))


class EmailRetry(Exception):
    """Raised by the job so procrastinate retries it (never carries content)."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__("retry")
        self.retry_after = retry_after


class EmailRetryStrategy(BaseRetryStrategy):
    def __init__(self, rand: Callable[[], float] = random.random):
        self._rand = rand

    def get_retry_decision(self, *, exception, job):
        if job.attempts + 1 >= MAX_ATTEMPTS:
            return None
        return RetryDecision(retry_in={"seconds": backoff_seconds(job.attempts, self._rand)})
