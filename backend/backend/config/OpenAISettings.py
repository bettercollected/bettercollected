from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class OpenAISettings(StoreBackedSettings):
    API_KEY: Optional[str] = ""
    MODAL: Optional[str] = "gpt-5-mini-2025-08-07"

    model_config = SettingsConfigDict(env_prefix='OPENAI_')
