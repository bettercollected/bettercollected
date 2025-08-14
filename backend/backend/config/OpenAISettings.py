from typing import Optional

from pydantic import BaseSettings


class OpenAISettings(BaseSettings):
    API_KEY: Optional[str] = ""
    MODAL: Optional[str] = "gpt-5-mini-2025-08-07"

    class Config:
        env_prefix = "OPENAI_"
