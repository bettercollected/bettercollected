from pydantic import BaseSettings


class TemporalSettings(BaseSettings):
    server_uri: str = ""

    class Config:
        env_prefix = "TEMPORAL_"
