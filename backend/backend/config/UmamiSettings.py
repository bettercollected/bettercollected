from typing import Optional

from pydantic import BaseSettings


class UmamiSettings(BaseSettings):

    USERNAME: Optional[str] = ""
    PASSWORD: Optional[str] = ""
    WEBSITE_ID: Optional[str] = "305e6851-f6fc-4640-8cbf-6f749768d118"
    URL = "https://umami.sireto.io"

    class Config:
        env_prefix = "UMAMI_"
