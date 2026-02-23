"""Application configuration - FastAPI."""

import os
from pathlib import Path

from typing import Optional

from auth.config.apm_settings import APMSettings
from auth.config.database import MongoSettings
from auth.config.google_settings import GoogleSettings
from auth.config.mail_settings import MailSettings
from auth.config.sentry_setting import SentrySettings
from auth.config.stripe import StripeSettings
from auth.config.typeform_settings import TypeformSettings
from auth.version import __version__
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


default_dot_env_path = (
    Path(os.path.abspath(os.path.dirname(__file__)))
    .parent.parent.absolute()
    .joinpath(".env")
)
load_dotenv(os.getenv("DOTENV_PATH", default_dot_env_path))


class Application(BaseSettings):
    """Define application configuration model."""

    DEBUG: Optional[bool] = True
    API_TITLE: Optional[str] = "auth"
    API_VERSION: Optional[str] = __version__
    API_ROOT_PATH: Optional[str] = "/api/v1"
    API_ENVIRONMENT: Optional[str] = "local"
    # All your additional application configuration should go either here or in
    # separate file in this submodule.

    apm_settings: APMSettings = APMSettings()
    mongo_settings: MongoSettings = MongoSettings()
    google_settings: GoogleSettings = GoogleSettings()
    typeform_settings: TypeformSettings = TypeformSettings()
    mail_settings: MailSettings = MailSettings()
    stripe_settings: StripeSettings = StripeSettings()
    sentry_settings: SentrySettings = SentrySettings()

    ORGANIZATION_NAME: Optional[str] = "Better Collected"
    AUTH_JWT_SECRET: str
    AUTH_AES_HEX_KEY: str
    CLIENT_ADMIN_URL: Optional[str] = "http://localhost:3000"

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Application()
