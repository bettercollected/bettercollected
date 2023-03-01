import string
import calendar
import secrets
from datetime import datetime, timedelta
import os

from fastapi_mail import ConnectionConfig, FastMail

from auth.config import settings


class MailService:
    def __init__(
        self,
        user=settings.mail_settings.user,
        password=settings.mail_settings.password,
        sender=settings.mail_settings.sender,
        smtp_port=settings.mail_settings.smtp_port,
        smtp_server=settings.mail_settings.smtp_server,
        organization_name=settings.organization_name,
        mail_tls=True,
        mail_ssl=False,
    ):
        mail_config = ConnectionConfig(
            MAIL_USERNAME=user,
            MAIL_PASSWORD=password,
            MAIL_FROM=sender,
            MAIL_PORT=smtp_port,
            MAIL_SERVER=smtp_server,
            MAIL_FROM_NAME=organization_name,
            MAIL_STARTTLS=mail_tls,
            MAIL_SSL_TLS=mail_ssl,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER=os.getenv("TEMPLATE_FOLDER", "auth/app/templates"),
        )
        self.fast_mail = FastMail(mail_config)

    async def send_async_mail(self, message, template_name="verification_code.html"):
        await self.fast_mail.send_message(message=message, template_name=template_name)
