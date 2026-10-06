"""Application configuration - FastAPI."""

import os
from pathlib import Path

from typing import Optional

from auth.config.apm_settings import APMSettings
from auth.config.database import MongoSettings
from auth.config.google_settings import GoogleSettings
from auth.config.mail_settings import MailSettings
from auth.config.sentry_setting import SentrySettings
from auth.config.sso_settings import SSOSettings
from auth.config.stripe import StripeSettings
from auth.config.typeform_settings import TypeformSettings
from auth.version import __version__
from dotenv import load_dotenv
from pydantic import AliasChoices, Field
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
    sso_settings: SSOSettings = SSOSettings()

    ORGANIZATION_NAME: Optional[str] = "Better Collected"
    AUTH_JWT_SECRET: str
    AUTH_AES_HEX_KEY: str
    CLIENT_ADMIN_URL: Optional[str] = "http://localhost:3000"
    # The respondent-facing (forms) host. Read from API_CLIENT_URL too, the
    # backend's name for it, so one shared env file sets both. Notification
    # mails only link to this host or CLIENT_ADMIN_URL.
    CLIENT_URL: Optional[str] = Field(
        "", validation_alias=AliasChoices("CLIENT_URL", "API_CLIENT_URL")
    )
    # Comma-separated emails that are platform admins (ADMIN role), on top of
    # any ADMIN stored on the user; see app/services/platform_admins.py.
    PLATFORM_ADMIN_EMAILS: Optional[str] = ""
    # Comma-separated URL prefixes of this instance's public storage (the
    # backend's AWS_PUBLIC_URL or AWS_ENDPOINT_URL, plus "/<bucket>/public/").
    # A workspace image the backend passes for a verification-code mail is
    # shown only from there; anything else falls back to an initial.
    MAIL_IMAGE_URL_PREFIXES: Optional[str] = (
        "https://s3.eu-central-1.wasabisys.com/bettercollected/public/"
    )
    # Comma-separated URL prefixes an inviter's avatar may also load from in
    # invitation mails: Google sign-in stores its userinfo "picture", served
    # from lh3.googleusercontent.com. Any other avatar shows an initial.
    MAIL_AVATAR_URL_PREFIXES: Optional[str] = "https://lh3.googleusercontent.com/"
    # Shared with the backend (and integrations/google): every route except
    # /ready and POST /stripe/webhooks needs it in X-Internal-Key
    # (controllers/internal_key.py). Named after the first route it guarded;
    # kept for compatibility. Unset = those routes answer 503.
    AUTH_INTERNAL_NOTIFY_KEY: Optional[str] = ""

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Application()
