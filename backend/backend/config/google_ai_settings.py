from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class GoogleAISettings(StoreBackedSettings):
    API_KEY: Optional[str] = ""
    MODEL: Optional[str] = "gemini-2.0-flash"

    model_config = SettingsConfigDict(env_prefix="GOOGLE_AI_")
