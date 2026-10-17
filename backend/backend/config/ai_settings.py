from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Cross-provider AI configuration.

    DEFAULT_PROVIDER picks which registered provider serves requests that
    don't name one ("openai" | "google" | "compatible").

    The COMPAT_* trio points at any OpenAI-compatible endpoint (Ollama, vLLM,
    LM Studio, OpenRouter, …) — the self-hosting story: bring your own model
    and no prompt ever leaves your infrastructure.

    The rest bounds what one AI request may cost (backend/AGENTS.md "AI
    limits"): output tokens, time, requests per user and workspace, and an
    optional daily budget per workspace.
    """

    DEFAULT_PROVIDER: Optional[str] = "openai"
    COMPAT_BASE_URL: Optional[str] = ""
    COMPAT_API_KEY: Optional[str] = "not-needed"  # many local servers ignore it
    COMPAT_MODEL: Optional[str] = ""
    # whether the compatible endpoint's model accepts images (PDF form import)
    COMPAT_VISION: Optional[bool] = False
    # ask the compatible endpoint for JSON mode (response_format json_object);
    # turn off for a server that refuses it. Replies are validated either way.
    COMPAT_JSON_MODE: bool = True

    # Time: one HTTP request to the provider, one whole AI call (its client
    # retries included), one outline (its corrective retry included), and all
    # the gap-filling calls of one build together (it then builds with what
    # was filled).
    REQUEST_TIMEOUT_SECONDS: float = 60
    CALL_TIMEOUT_SECONDS: float = 120
    GENERATION_TIMEOUT_SECONDS: float = 240
    GAP_FILL_DEADLINE_SECONDS: float = 120
    # the provider client's own retries of a failed request
    CLIENT_MAX_RETRIES: int = 1

    # Output tokens per call type (reasoning models count their reasoning too).
    MAX_OUTPUT_TOKENS_GENERATE: int = 16000
    MAX_OUTPUT_TOKENS_CHAT: int = 8000
    MAX_OUTPUT_TOKENS_REVIEW: int = 8000
    MAX_OUTPUT_TOKENS_INSIGHTS: int = 4000
    MAX_OUTPUT_TOKENS_MEMORY: int = 1000

    # Requests to the AI endpoints per window (0 turns a limit off).
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_PER_USER: int = 10
    RATE_LIMIT_PER_WORKSPACE: int = 30
    # applying a review's fix calls no provider, so it has its own allowance
    RATE_LIMIT_FIX_PER_USER: int = 60

    # How long a chat proposal (the editor's propose mode) can be accepted.
    PROPOSAL_TTL_SECONDS: int = 3600

    # Daily budget per workspace (UTC day). Requests and tokens are always
    # counted; 0 means no cap.
    DAILY_REQUEST_BUDGET: int = 0
    DAILY_TOKEN_BUDGET: int = 0

    model_config = SettingsConfigDict(env_prefix="AI_")
