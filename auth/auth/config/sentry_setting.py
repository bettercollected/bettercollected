from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class SentrySettings(StoreBackedSettings):
    DSN: Optional[str] = ""
    DEBUG: Optional[bool] = False

    model_config = SettingsConfigDict(env_prefix="SENTRY_")
