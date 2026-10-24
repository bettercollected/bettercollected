from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class BrevoSettings(StoreBackedSettings):
    tracker_key: Optional[str] = ""
    tracker_api_url: Optional[str] = ""
    # A Brevo API (v3) key, separate from the tracker key: used only to erase
    # a deleted account's contact (DELETE /v3/contacts/{email}). Empty = the
    # erasure is skipped and logged.
    contacts_api_key: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="BREVO_")
