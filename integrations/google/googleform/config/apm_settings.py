from typing import Optional

from pydantic_settings import BaseSettings


class APMSettings(BaseSettings):
    # Optional[str], not str: these are unset unless ELASTIC_APM_* env vars
    # are provided. Pydantic v2 rejects a bare `str` field defaulting to None
    # (v1 tolerated it), which crashed the service on import after the pydantic
    # v1 → v2 dependency bump.
    api_key: Optional[str] = None
    service_name: Optional[str] = None
    server_url: Optional[str] = None

    class Config:
        env_prefix = "ELASTIC_APM_"
