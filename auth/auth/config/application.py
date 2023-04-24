"""Application configuration - FastAPI."""
import os
from pathlib import Path

from auth.config.database import MongoSettings
from auth.config.google_settings import GoogleSettings
from auth.config.mail_settings import MailSettings
from auth.config.stripe import StripeSettings
from auth.config.typeform_settings import TypeformSettings
from auth.version import __version__

from dotenv import load_dotenv

from pydantic import BaseSettings

default_dot_env_path = (
    Path(os.path.abspath(os.path.dirname(__file__)))
    .parent.parent.absolute()
    .joinpath(".env")
)
load_dotenv(os.getenv("DOTENV_PATH", default_dot_env_path))


class Application(BaseSettings):
    """Define application configuration model."""

    DEBUG: bool = True
    API_TITLE: str = "auth"
    API_VERSION: str = __version__
    API_ROOT_PATH: str = ""
    # All your additional application configuration should go either here or in
    # separate file in this submodule.
    mongo_settings: MongoSettings = MongoSettings()
    google_settings: GoogleSettings = GoogleSettings()
    typeform_settings: TypeformSettings = TypeformSettings()
    mail_settings: MailSettings = MailSettings()
    stripe_settings: StripeSettings = StripeSettings()

    ORGANIZATION_NAME: str = "Better Collected"
    AUTH_JWT_SECRET: str
    AUTH_AEX_HEX_KEY: str
    CLIENT_ADMIN_URL: str = "http://localhost:3000"

    class Config:
        """Config sub-class needed to customize BaseSettings settings.

        Attributes:
            case_sensitive (bool): When case_sensitive is True, the environment
                variable names must match field names (optionally with a prefix)
            env_prefix (str): The prefix for environment variable.

        Resources:
            https://pydantic-docs.helpmanual.io/usage/settings/

        """

        case_sensitive = True


settings = Application()
