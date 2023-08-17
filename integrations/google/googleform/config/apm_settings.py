from pydantic import BaseSettings


class APMSettings(BaseSettings):
    api_key: str = None
    service_name: str = None
    server_url: str = None

    class Config:
        env_prefix = "ELASTIC_APM_"
