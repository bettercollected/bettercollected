from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    API_KEY: Optional[str] = ""
    MODAL: Optional[str] = "gpt-5-mini-2025-08-07"

    model_config = SettingsConfigDict(env_prefix='OPENAI_')
