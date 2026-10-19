from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class UnsplashSettings(StoreBackedSettings):
    # The backend never reads it (the webapp's photo picker does, from its own environment): a
    # required field here stopped every stack that had not set it, a new install included.
    ACCESS_KEY: str = ""
    BASE_URL: str = "https://api.unsplash.com"
    PER_PAGE: int = 10

    model_config = SettingsConfigDict(env_prefix="UNSPLASH_", case_sensitive=False)
