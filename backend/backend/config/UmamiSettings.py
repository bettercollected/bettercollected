from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class UmamiSettings(BaseSettings):

    USERNAME: Optional[str] = ""
    PASSWORD: Optional[str] = ""
    WEBSITE_ID: Optional[str] = "305e6851-f6fc-4640-8cbf-6f749768d118"
    URL: str = "https://umami.sireto.io"

    model_config = SettingsConfigDict(env_prefix="UMAMI_")
