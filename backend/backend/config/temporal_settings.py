from pydantic import BaseSettings


class TemporalSettings(BaseSettings):
    server_uri: str = ""
    api_key: str = "random_api_key"

    class Config:
        env_prefix = "TEMPORAL_"
