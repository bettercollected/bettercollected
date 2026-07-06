from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class UmamiSettings(BaseSettings):

    USERNAME: Optional[str] = ""
    PASSWORD: Optional[str] = ""
    WEBSITE_ID: Optional[str] = ""
    URL: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="UMAMI_")

    @property
    def is_configured(self) -> bool:
        return bool(self.URL and self.USERNAME and self.PASSWORD and self.WEBSITE_ID)
