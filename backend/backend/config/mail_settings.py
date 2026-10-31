"""The instance's outgoing mail server (``MAIL_*``), as the auth service reads
it: the email actions send through it (``services/email_actions``). Nothing is
read per workspace or per form."""

from typing import Optional

from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class MailSettings(StoreBackedSettings):
    user: Optional[str] = ""
    password: Optional[str] = ""
    smtp_server: Optional[str] = ""
    smtp_port: Optional[int] = 587
    sender: Optional[str] = ""
    starttls: Optional[bool] = True
    ssl_tls: Optional[bool] = False
    use_credentials: Optional[bool] = True
    validate_certs: Optional[bool] = True

    model_config = SettingsConfigDict(env_prefix="MAIL_")
