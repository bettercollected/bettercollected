from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class BrevoSettings(StoreBackedSettings):
    tracker_key: Optional[str] = ""
    tracker_api_url: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix='BREVO_')
