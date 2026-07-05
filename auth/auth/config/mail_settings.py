from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class MailSettings(BaseSettings):
    user: Optional[str] = ""
    password: Optional[str] = ""
    smtp_server: Optional[str] = ""
    smtp_port: Optional[int] = 587
    sender: Optional[str] = ""
    # Transport flags. Defaults keep production behaviour (STARTTLS + auth).
    # For a local catch-all like Mailpit set MAIL_STARTTLS/MAIL_USE_CREDENTIALS/
    # MAIL_VALIDATE_CERTS to false.
    starttls: Optional[bool] = True
    ssl_tls: Optional[bool] = False
    use_credentials: Optional[bool] = True
    validate_certs: Optional[bool] = True

    model_config = SettingsConfigDict(env_prefix="MAIL_")
