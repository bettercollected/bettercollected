from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class APMSettings(StoreBackedSettings):
    api_key: Optional[str] = None
    service_name: Optional[str] = None
    server_url: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="ELASTIC_APM_")
