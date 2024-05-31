from typing import Optional

from pydantic import BaseSettings


class BrevoSettings(BaseSettings):
    tracker_key: Optional[str] = ""
    tracker_api_url: Optional[str] = ""

    class Config:
        env_prefix = "BREVO_"
