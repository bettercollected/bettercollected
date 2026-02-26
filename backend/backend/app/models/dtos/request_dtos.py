from enum import Enum
from typing import Optional

from pydantic import BaseModel


class AIProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"


class PriceIdRequest(BaseModel):
    price_id: str


class CreateFormWithAI(BaseModel):
    prompt: str
    provider: AIProvider = AIProvider.OPENAI
