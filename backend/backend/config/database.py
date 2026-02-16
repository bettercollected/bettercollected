from pydantic_settings import BaseSettings, SettingsConfigDict


class MongoSettings(BaseSettings):
    DB: str = "bettercollected_backend"
    URI: str = "mongodb://localhost"

    model_config = SettingsConfigDict(case_sensitive=True, env_prefix="MONGO_")
