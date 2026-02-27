from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class MongoSettings(BaseSettings):
    DB: Optional[str] = "bettercollected_auth"
    URI: Optional[str] = "mongodb://localhost"

    model_config = SettingsConfigDict(case_sensitive=True, env_prefix="MONGO_")
