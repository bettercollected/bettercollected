from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class MongoSettings(StoreBackedSettings):
    DB: Optional[str] = "bettercollected_auth"
    URI: Optional[str] = "mongodb://localhost"

    model_config = SettingsConfigDict(case_sensitive=True, env_prefix="MONGO_")
