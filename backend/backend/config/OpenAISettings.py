from typing import Optional

from pydantic import BaseSettings


class OpenAISettings(BaseSettings):
    API_KEY: Optional[str] = ""

    class Config:
        env_prefix = "OPENAI_"
