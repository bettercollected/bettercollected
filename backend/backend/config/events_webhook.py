from typing import Optional

from pydantic_settings import BaseSettings


class EventsWebhook(BaseSettings):
    url: Optional[str]
    enabled: Optional[bool] = False

    class Config:
        env_prefix = "EVENT_WEBHOOK_"
