from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class UnsplashSettings(BaseSettings):
    ACCESS_KEY: Optional[str] = ""
    BASE_URL: str = "https://api.unsplash.com"
    PER_PAGE: int = 10

    model_config = SettingsConfigDict(env_prefix="UNSPLASH_")
