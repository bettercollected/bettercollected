from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class TemporalSettings(BaseSettings):
    server_uri: str = "localhost:7233"
    # Shared with the Temporal worker and the actions-executor (API_KEY there);
    # no default: unset means the internal job routes answer 503
    # (backend.app.services.internal_job_key).
    api_key: str = ""
    namespace: str = "default"
    template_preview_queue: Optional[str] = "template_preview_queue"
    worker_queue: str = "default"
    action_queue: str = "actions"
    csv_queue: str = "csv_worker"
    add_import_schedules: bool = False

    model_config = SettingsConfigDict(env_prefix='TEMPORAL_')
