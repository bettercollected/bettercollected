from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class MongoSettings(StoreBackedSettings):
    DB: str = "bettercollected_backend"
    URI: str = "mongodb://localhost"

    model_config = SettingsConfigDict(case_sensitive=True, env_prefix="MONGO_")
