from functools import lru_cache

from pydantic import BaseSettings

from settings.api import ApiSettings
from settings.mongo import MongoSettings
from settings.scheduler import SchedulerSettings


__all__ = "settings"


class Settings(BaseSettings):
    """
    Class representing the app's settings.

    This class inherits from BaseSettings, which provides some
    utility functions and a default implementation for loading
    settings from environment variables.

    Attributes:
        exclude_none_in_all_response_models: bool: Whether to exclude
            fields with value None in all response models.
        api_settings: ApiSettings: Settings related to the API.
        mongo_settings: MongoSettings: Settings related to MongoDB.
        scheduler_settings: SchedulerSettings: Settings related to
            the scheduler.

    Methods:
        is_development: Return whether the current environment is development.
    """

    exclude_none_in_all_response_models: bool = True

    api_settings: ApiSettings = ApiSettings()
    mongo_settings: MongoSettings = MongoSettings()
    scheduler_settings: SchedulerSettings = SchedulerSettings()

    def is_development(self):
        return self.api_settings.environment == "development"


@lru_cache()
def get_settings():
    """
    This function retrieves the app's settings object.

    The function is decorated with @lru_cache, which means that the
    result of the function is cached. Subsequent calls to the function
    will return the same result, without executing the function again.
    This is useful for improving the performance of the app, as it
    avoids unnecessarily recomputing the result.

    The function returns an instance of the Settings class.
    """
    return Settings()


settings = get_settings()
