from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class SentrySettings(BaseSettings):
    DSN: Optional[str] = ""
    DEBUG: Optional[bool] = False

    model_config = SettingsConfigDict(env_prefix="SENTRY_")
