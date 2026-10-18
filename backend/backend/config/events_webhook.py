from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class EventsWebhook(StoreBackedSettings):
    url: Optional[str] = None
    enabled: Optional[bool] = False

    model_config = SettingsConfigDict(env_prefix='EVENT_WEBHOOK_')
