from pydantic_settings import BaseSettings, SettingsConfigDict


class SentrySettings(BaseSettings):
    DSN: str = ""
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_prefix='SENTRY_')
