from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AIProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    # Any OpenAI-compatible endpoint (Ollama, vLLM, ...) — the self-host option.
    COMPATIBLE = "compatible"


class PriceIdRequest(BaseModel):
    price_id: str


# what one generation request may ask, in characters (it is sent with the
# system prompt and tool results on every round trip)
AI_PROMPT_MAX_LENGTH = 8000


class CreateFormWithAI(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=AI_PROMPT_MAX_LENGTH)
    # None -> settings.ai.DEFAULT_PROVIDER decides.
    provider: Optional[AIProvider] = None
