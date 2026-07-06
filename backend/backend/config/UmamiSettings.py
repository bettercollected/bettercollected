from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class UmamiSettings(BaseSettings):

    USERNAME: Optional[str] = ""
    PASSWORD: Optional[str] = ""
    WEBSITE_ID: Optional[str] = ""
    URL: Optional[str] = ""
    # Used only to auto-provision a website (find-or-create by this name) when
    # WEBSITE_ID isn't set — see umami_client.provision_umami_website. Lets
    # self-hosters skip creating a website by hand in the Umami UI.
    WEBSITE_NAME: Optional[str] = "BetterCollected"

    model_config = SettingsConfigDict(env_prefix="UMAMI_")

    @property
    def has_credentials(self) -> bool:
        return bool(self.URL and self.USERNAME and self.PASSWORD)

    @property
    def is_configured(self) -> bool:
        return bool(self.has_credentials and self.WEBSITE_ID)
