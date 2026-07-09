from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Cross-provider AI configuration.

    DEFAULT_PROVIDER picks which registered provider serves requests that
    don't name one ("openai" | "google" | "compatible").

    The COMPAT_* trio points at any OpenAI-compatible endpoint (Ollama, vLLM,
    LM Studio, OpenRouter, …) — the self-hosting story: bring your own model
    and no prompt ever leaves your infrastructure.
    """

    DEFAULT_PROVIDER: Optional[str] = "openai"
    COMPAT_BASE_URL: Optional[str] = ""
    COMPAT_API_KEY: Optional[str] = "not-needed"  # many local servers ignore it
    COMPAT_MODEL: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="AI_")
