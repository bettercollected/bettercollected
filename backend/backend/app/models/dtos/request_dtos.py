from enum import Enum
from typing import Optional

from pydantic import BaseModel


class AIProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    # Any OpenAI-compatible endpoint (Ollama, vLLM, ...) — the self-host option.
    COMPATIBLE = "compatible"


class PriceIdRequest(BaseModel):
    price_id: str


class CreateFormWithAI(BaseModel):
    prompt: str
    # None -> settings.ai.DEFAULT_PROVIDER decides.
    provider: Optional[AIProvider] = None
