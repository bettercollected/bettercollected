"""Abstract interface for AI-based form generation providers."""

import abc
import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from loguru import logger

from backend.app.services.ai.errors import AIError, ai_timeout, ai_unavailable

# form import page analysis: bounded answer size and wall-clock time per call
PAGE_MAX_TOKENS = 16000
PAGE_TIMEOUT_S = 120

T = TypeVar("T")


def _is_timeout(error: BaseException) -> bool:
    # openai.APITimeoutError, google.api_core DeadlineExceeded, httpx timeouts
    return any(
        "Timeout" in kind.__name__ or kind.__name__ == "DeadlineExceeded"
        for kind in type(error).__mro__
    )


async def call_provider(call: Callable[[], Awaitable[T]], timeout: float) -> T:
    """Run one provider call within ``timeout`` seconds (its client retries
    included). A timeout becomes 504 ``ai_timeout``, any other provider
    failure 502 ``ai_unavailable``; only the error's type is logged, never
    its message (it can quote the request)."""
    try:
        return await asyncio.wait_for(call(), timeout=timeout)
    except AIError:
        raise
    except (asyncio.TimeoutError, TimeoutError):
        raise ai_timeout() from None
    except Exception as error:  # noqa: BLE001 — the provider boundary
        if _is_timeout(error):
            raise ai_timeout() from None
        logger.warning("AI provider call failed ({})", type(error).__name__)
        raise ai_unavailable() from None


class AIFormProvider(abc.ABC):
    """Base contract that all AI provider implementations must satisfy.

    Every call is bounded (backend/AGENTS.md "AI limits"): output tokens per
    call type, a timeout per request and per call, and form generation's
    tool loop by AI_MAX_TOOL_ITERATIONS / AI_MAX_TOOL_CALLS and
    AI_GENERATION_TIMEOUT_SECONDS. Providers report each call's tokens with
    ``services.ai.usage.record_tokens``.
    """

    @abc.abstractmethod
    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        """Generate a raw form dict from a natural-language prompt.

        The returned dict is validated (``services.ai.structured.GeneratedForm``)
        and is what ``OpenAIService.convert_openai_form_to_standard_form``
        consumes: title, description, theme_name, welcome_image_url,
        cover_image_url and the fields.

        Args:
            prompt: Natural-language description of the desired form.

        Returns:
            Intermediate form dict.
        """

    async def chat(
        self,
        system: str,
        messages: "list[dict]",
        *,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Multi-turn chat completion (used by AI form editing).

        Args:
            system: System prompt.
            messages: [{"role": "user"|"assistant", "content": str}, ...]
                ending with the latest user message.
            max_output_tokens: Output token cap (default AI_MAX_OUTPUT_TOKENS_CHAT).
            json_mode: Ask for a JSON object where the provider supports it.
            json_schema: {"name", "schema"}: a strict JSON schema the reply
                must follow, where the provider supports structured output
                (others fall back to JSON mode; callers validate either way).

        Returns:
            The assistant's raw text reply.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support chat yet.")

    #: whether ``analyze_page`` can look at the page image
    supports_vision: bool = False

    async def analyze_page(
        self, system: str, prompt: str, image_png: "bytes | None", schema: dict
    ) -> dict:
        """One structured-output call about a document page (PDF form import).

        Args:
            system: System prompt.
            prompt: The page description (text, layout items, instructions).
            image_png: The rendered page, or None when the provider has no vision.
            schema: JSON schema the answer must follow.

        Returns:
            The parsed JSON answer.
        """
        raise NotImplementedError(f"{type(self).__name__} cannot analyze pages yet.")
