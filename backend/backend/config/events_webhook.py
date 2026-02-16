from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class EventsWebhook(BaseSettings):
    url: Optional[str]
    enabled: Optional[bool] = False

    model_config = SettingsConfigDict(env_prefix='EVENT_WEBHOOK_')
