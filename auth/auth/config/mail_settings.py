from typing import Optional

from pydantic import BaseSettings


class MailSettings(BaseSettings):
    user: str = ""
    password: str = ""
    smtp_server: str = ""
    smtp_port: Optional[int] = 587
    sender: str = ""

    class Config:
        env_prefix = "MAIL_"
