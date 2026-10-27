"""The delivery job's retry schedule: 6 attempts, with waits of 1 minute,
5 minutes, 30 minutes, 2 hours and 6 hours between them (about 8.6 hours in
all), then the delivery is ``failed`` and visible with a retry button."""

from typing import Optional

RETRY_WAITS = (60, 300, 1800, 7200, 21600)
MAX_ATTEMPTS = len(RETRY_WAITS) + 1


class RegistrationRetry(Exception):
    """Raised by the job so procrastinate retries it (never carries content)."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__("retry")
        self.retry_after = retry_after
