from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class APMSettings(BaseSettings):
    api_key: Optional[str] = None
    service_name: Optional[str] = None
    server_url: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="ELASTIC_APM_")
