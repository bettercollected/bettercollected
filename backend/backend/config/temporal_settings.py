from pydantic import BaseSettings


class TemporalSettings(BaseSettings):
    server_uri: str = ""
    api_key: str = "random_api_key"
    namespace: str = "default"
    worker_queue: str = "default"

    class Config:
        env_prefix = "TEMPORAL_"
