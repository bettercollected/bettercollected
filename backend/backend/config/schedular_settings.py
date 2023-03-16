from pydantic import BaseSettings


class SchedularSettings(BaseSettings):
    ENABLED: bool = True
    INTERVAL_MINUTES: int = 2

    class Config:
        env_prefix = "SCHEDULAR_"
