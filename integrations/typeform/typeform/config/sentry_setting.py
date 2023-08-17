from pydantic import BaseSettings


class SentrySettings(BaseSettings):
    DSN: str = ""
    DEBUG: bool = False

    class Config:
        env_prefix = "SENTRY_"
