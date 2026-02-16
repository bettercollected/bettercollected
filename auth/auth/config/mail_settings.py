from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class MailSettings(BaseSettings):
    user: Optional[str] = ""
    password: Optional[str] = ""
    smtp_server: Optional[str] = ""
    smtp_port: Optional[int] = 587
    sender: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="MAIL_")
