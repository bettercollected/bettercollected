from pydantic_settings import BaseSettings, SettingsConfigDict


class SchedularSettings(BaseSettings):
    ENABLED: bool = True
    INTERVAL_MINUTES: int = 1

    model_config = SettingsConfigDict(env_prefix='SCHEDULAR_')
