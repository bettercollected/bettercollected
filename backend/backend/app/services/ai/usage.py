"""Rate limits and the daily budget of the AI endpoints.

``AIUsageGuard.admit`` runs once per AI request (from
``OpenAIService.provider_for_workspace``, after the membership and opt-in
checks): a fixed window per user and per workspace, then the workspace's
daily request and token budget. All counters live in the shared
``rate_limit_counters`` (services/rate_limiter.py), keyed by hashes of the
ids, so every replica counts together.

Tokens are counted where the provider reports usage: ``bind_usage`` ties
the current task to a workspace, and each provider call adds its tokens
with ``record_tokens``. Only counts and ids are ever recorded.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from loguru import logger

from backend.app.services.ai.errors import ai_daily_limit, ai_rate_limited
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.config import settings

USER_SCOPE = "ai:user"
WORKSPACE_SCOPE = "ai:workspace"
FIX_SCOPE = "ai:fix:user"
BUDGET_REQUESTS_SCOPE = "ai:budget:requests"
BUDGET_TOKENS_SCOPE = "ai:budget:tokens"
DAY_SECONDS = 86400
# counting without a cap: a limit no counter reaches
_UNCAPPED = 2**62


@dataclass(frozen=True)
class _Meter:
    guard: "AIUsageGuard"
    workspace_id: str


_meter: ContextVar[Optional[_Meter]] = ContextVar("ai_usage_meter", default=None)


def bind_usage(guard: Optional["AIUsageGuard"], workspace_id: Any) -> None:
    """Count the tokens of the provider calls that follow (in this task and
    the tasks it starts) against ``workspace_id``'s daily budget."""
    _meter.set(_Meter(guard, str(workspace_id)) if guard else None)


async def record_tokens(tokens: Optional[int]) -> None:
    """Add one provider call's reported tokens to the bound workspace.
    Never fails the call: a counter that cannot be written is logged by
    error type only."""
    meter = _meter.get()
    if meter is None or not tokens or tokens <= 0:
        return
    try:
        await meter.guard.add_tokens(meter.workspace_id, int(tokens))
    except Exception as error:  # noqa: BLE001 — accounting must not break AI calls
        logger.warning("AI token usage not recorded ({})", type(error).__name__)


class AIUsageGuard:
    def __init__(self, limiter: FixedWindowRateLimiter):
        self._limiter = limiter

    async def admit(self, workspace_id: Any, user_id: Optional[Any]) -> None:
        """One AI request of ``user_id`` (None for work without a person,
        such as an import job) in ``workspace_id``: 429 ``ai_rate_limited``
        over a window limit, 429 ``ai_daily_limit`` over the daily budget."""
        config = settings.ai
        window = config.RATE_LIMIT_WINDOW_SECONDS
        if user_id is not None and config.RATE_LIMIT_PER_USER > 0:
            verdict = await self._limiter.hit(
                USER_SCOPE, str(user_id), config.RATE_LIMIT_PER_USER, window
            )
            if not verdict.allowed:
                raise ai_rate_limited(verdict.retry_after)
        if config.RATE_LIMIT_PER_WORKSPACE > 0:
            verdict = await self._limiter.hit(
                WORKSPACE_SCOPE,
                str(workspace_id),
                config.RATE_LIMIT_PER_WORKSPACE,
                window,
            )
            if not verdict.allowed:
                raise ai_rate_limited(verdict.retry_after)
        await self._spend_request(str(workspace_id))

    async def admit_fix(self, workspace_id: Any, user_id: Any) -> None:
        """Applying a review's fix: no provider call, so its own allowance
        per user and no budget."""
        config = settings.ai
        if config.RATE_LIMIT_FIX_PER_USER <= 0:
            return
        verdict = await self._limiter.hit(
            FIX_SCOPE,
            f"{workspace_id}\n{user_id}",
            config.RATE_LIMIT_FIX_PER_USER,
            config.RATE_LIMIT_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise ai_rate_limited(verdict.retry_after)

    async def _spend_request(self, workspace_id: str) -> None:
        config = settings.ai
        requests = await self._limiter.hit(
            BUDGET_REQUESTS_SCOPE, workspace_id, _UNCAPPED, DAY_SECONDS
        )
        if config.DAILY_REQUEST_BUDGET > 0 and (
            requests.count > config.DAILY_REQUEST_BUDGET
        ):
            raise ai_daily_limit(requests.retry_after)
        if config.DAILY_TOKEN_BUDGET > 0:
            tokens = await self._limiter.hit(
                BUDGET_TOKENS_SCOPE, workspace_id, _UNCAPPED, DAY_SECONDS, amount=0
            )
            if tokens.count >= config.DAILY_TOKEN_BUDGET:
                raise ai_daily_limit(tokens.retry_after)

    async def add_tokens(self, workspace_id: Any, tokens: int) -> None:
        await self._limiter.hit(
            BUDGET_TOKENS_SCOPE, str(workspace_id), _UNCAPPED, DAY_SECONDS, tokens
        )

    async def usage_today(self, workspace_id: Any) -> Tuple[int, int]:
        """(requests, tokens) counted for the workspace today (UTC)."""
        requests = await self._limiter.hit(
            BUDGET_REQUESTS_SCOPE, str(workspace_id), _UNCAPPED, DAY_SECONDS, 0
        )
        tokens = await self._limiter.hit(
            BUDGET_TOKENS_SCOPE, str(workspace_id), _UNCAPPED, DAY_SECONDS, 0
        )
        return requests.count, tokens.count
