from typing import Optional

from pydantic import BaseSettings


class OpenAISettings(BaseSettings):
    API_KEY: Optional[str] = ""
    MODAL: Optional[str] = "gpt-4o"

    class Config:
        env_prefix = "OPENAI_"
