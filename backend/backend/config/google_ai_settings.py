from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleAISettings(BaseSettings):
    API_KEY: Optional[str] = ""
    MODEL: Optional[str] = "gemini-2.0-flash"

    model_config = SettingsConfigDict(env_prefix="GOOGLE_AI_")
