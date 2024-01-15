from pydantic import BaseSettings


class TemporalSettings(BaseSettings):
    server_uri: str = ""
    api_key: str = "random_api_key"
    namespace: str = "default"
    worker_queue: str = "default"
    action_queue: str = "actions"
    csv_queue: str = "csv_worker"
    add_import_schedules: bool = False

    class Config:
        env_prefix = "TEMPORAL_"
