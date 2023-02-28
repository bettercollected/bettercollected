from pydantic import BaseSettings


class MailSettings(BaseSettings):
    user: str = ""
    password: str = ""
    smtp_server: str = "mail.sireto.io"
    smtp_port: int = 587
    sender: str = "BetterCollected<bettercollected@gmail.com>"

    class Config:
        env_prefix = "MAIL_"
