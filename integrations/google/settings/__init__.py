from functools import lru_cache

from pydantic import BaseSettings

from settings.api import ApiSettings
from settings.mongo import MongoSettings
from settings.scheduler import SchedulerSettings


__all__ = "settings"


class Settings(BaseSettings):
    exclude_none_in_all_response_models: bool = True

    api_settings: ApiSettings = ApiSettings()
    mongo_settings: MongoSettings = MongoSettings()
    scheduler_settings: SchedulerSettings = SchedulerSettings()

    def is_development(self):
        return self.api_settings.environment == "development"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
