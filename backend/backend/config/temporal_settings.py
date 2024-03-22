from typing import Optional

from pydantic import BaseSettings


class TemporalSettings(BaseSettings):
    server_uri: str = ""
    api_key: str = "random_api_key"
    namespace: str = "default"
    template_preview_queue: Optional[str] = "template_preview_queue"
    worker_queue: str = "default"
    action_queue: str = "actions"
    csv_queue: str = "csv_worker"
    add_import_schedules: bool = False

    class Config:
        env_prefix = "TEMPORAL_"
