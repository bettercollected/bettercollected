from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class BrevoSettings(BaseSettings):
    tracker_key: Optional[str] = ""
    tracker_api_url: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix='BREVO_')
