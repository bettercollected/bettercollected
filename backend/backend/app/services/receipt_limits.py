"""Rate limits of the public receipt routes.

``GET`` and ``DELETE /workspaces/{id}/submissions/by-uuid/{number}`` need no
sign-in: the receipt number is the only credential. These limits make guessing
numbers slow without getting in the way of a respondent opening their own
receipt. All counters live in the database (``FixedWindowRateLimiter``), so
every replica shares them.

Per client address (an IPv6 client by its /64, ``rate_limit_key``), in each
window of ``API_RECEIPT_WINDOW_SECONDS``:

* ``API_RECEIPT_REQUESTS_PER_WINDOW`` requests per route, counted before the
  number is looked up;
* ``API_RECEIPT_MISSES_PER_WINDOW`` numbers that were not found (404), both
  routes together. Once a client has used them up, every further lookup is
  refused until the window ends, found or not.

And for everyone together, ``API_RECEIPT_GLOBAL_MISSES_PER_WINDOW`` misses: an
emergency switch against guessing spread over many addresses, off (0) by
default. Once reached it refuses every receipt lookup, for everyone, until the
window ends; receipt numbers are uuid4, so it is not needed against guessing
one. While it is 0 its counter is never read or written (no shared row every
lookup would wait on). Each limit is off at 0.

A refused request answers 429 with ``Retry-After``. The limiter's keys are the
route and the client address only, never the receipt number, and the counter
ids are a keyed hash of those (no address is stored). Nothing here logs the
number or the address.
"""

from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import AsyncIterator, Optional

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.rate_limiter import FixedWindowRateLimiter, Verdict
from backend.app.utils.client_ip import rate_limit_key
from backend.config import settings  # noqa: F401  (builds the settings and the live() groups)
from common.settings.loader import live

READ = "receipt-read"
DELETION_REQUEST = "receipt-deletion-request"
ROUTES = frozenset({READ, DELETION_REQUEST})
MISS_SCOPE = "receipt-miss"
GLOBAL_MISS_SCOPE = "receipt-miss-all"
GLOBAL_CLIENT = "*"


def _too_many(verdict: Verdict) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        content={
            "code": "rate_limited",
            "message": "Too many receipt lookups. Retry after "
            f"{verdict.retry_after} seconds.",
        },
        headers={"Retry-After": str(verdict.retry_after)},
    )


class ReceiptLimits:
    def __init__(self, rate_limiter: FixedWindowRateLimiter):
        self._limiter = rate_limiter

    @asynccontextmanager
    async def lookup(self, route: str, client: Optional[str]) -> AsyncIterator[None]:
        """Admit one lookup on ``route`` from ``client`` (raises 429), then
        count it as a miss when the body raises a 404."""
        if route not in ROUTES:
            raise ValueError(f"unknown receipt route: {route}")
        key = rate_limit_key(client)
        await self._admit(route, key)
        try:
            yield
        except HTTPException as refused:
            if refused.status_code == HTTPStatus.NOT_FOUND:
                await self._miss(key)
            raise

    async def _admit(self, route: str, key: str) -> None:
        api = live().api
        window = api.RECEIPT_WINDOW_SECONDS
        # every request, found or not, against its route's limit
        if api.RECEIPT_REQUESTS_PER_WINDOW > 0:
            verdict = await self._limiter.hit(
                route, key, api.RECEIPT_REQUESTS_PER_WINDOW, window
            )
            if not verdict.allowed:
                logger.info("Receipt lookup refused: too many requests")
                raise _too_many(verdict)
        # the misses so far (read, not counted): no lookup once they are used up
        if api.RECEIPT_MISSES_PER_WINDOW > 0:
            verdict = await self._limiter.hit(
                MISS_SCOPE, key, api.RECEIPT_MISSES_PER_WINDOW, window, amount=0
            )
            if verdict.count >= api.RECEIPT_MISSES_PER_WINDOW:
                logger.info("Receipt lookup refused: too many unknown numbers")
                raise _too_many(verdict)
        if api.RECEIPT_GLOBAL_MISSES_PER_WINDOW > 0:
            verdict = await self._limiter.hit(
                GLOBAL_MISS_SCOPE,
                GLOBAL_CLIENT,
                api.RECEIPT_GLOBAL_MISSES_PER_WINDOW,
                window,
                amount=0,
            )
            if verdict.count >= api.RECEIPT_GLOBAL_MISSES_PER_WINDOW:
                logger.warning(
                    "Receipt lookup refused: too many unknown numbers from all "
                    "clients together"
                )
                raise _too_many(verdict)

    async def _miss(self, key: str) -> None:
        api = live().api
        window = api.RECEIPT_WINDOW_SECONDS
        if api.RECEIPT_MISSES_PER_WINDOW > 0:
            await self._limiter.hit(
                MISS_SCOPE, key, api.RECEIPT_MISSES_PER_WINDOW, window
            )
        if api.RECEIPT_GLOBAL_MISSES_PER_WINDOW > 0:
            await self._limiter.hit(
                GLOBAL_MISS_SCOPE,
                GLOBAL_CLIENT,
                api.RECEIPT_GLOBAL_MISSES_PER_WINDOW,
                window,
            )
