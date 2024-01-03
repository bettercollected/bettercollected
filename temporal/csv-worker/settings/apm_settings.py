from pydantic.v1 import BaseSettings


class APMSettings(BaseSettings):
    api_key: str = "api-key"
    service_name: str = "temporal-worker"
    server_url: str = "https://apm.sireto.io"
    enabled: bool = False

    class Config:
        env_prefix = "ELASTIC_APM_"
