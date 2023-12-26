from typing import Optional

from pydantic import BaseSettings


class KafkaSettings(BaseSettings):
    server_url: Optional[str] = "localhost:9092"
    topic: Optional[str] = "bettercollected_events"
    enabled: Optional[bool] = False

    class Config:
        env_prefix = "KAFKA_"
