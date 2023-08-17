"""Application configuration - FastAPI."""

import os
from pathlib import Path

from backend.config.api_settings import ApiSettings
from backend.config.apm_settings import APMSettings
from backend.config.auth_settings import AuthSettings
from backend.config.aws import AWSSettings
from backend.config.database import MongoSettings
from backend.config.https_certificate import HttpsCertificateApiSettings
from backend.config.schedular_settings import SchedularSettings
from backend.config.sentry_setting import SentrySettings
from backend.config.temporal_settings import TemporalSettings
from dotenv import load_dotenv
from pydantic import BaseSettings

default_dot_env_path = (
    Path(os.path.abspath(os.path.dirname(__file__)))
    .parent.parent.absolute()
    .joinpath(".env")
)
load_dotenv(os.getenv("DOTENV_PATH", default_dot_env_path))


class Application(BaseSettings):
    """Define application configuration model.

    Constructor will attempt to determine the values of any fields not passed
    as keyword arguments by reading from the environment. Default values will
    still be used if the matching environment variable is not set.

    Attributes:
        DEBUG (bool): FastAPI logging level. You should disable this for
            production.
    """

    DEBUG: bool = True
    apm_settings: APMSettings = APMSettings()
    api_settings: ApiSettings = ApiSettings()
    auth_settings: AuthSettings = AuthSettings()
    mongo_settings: MongoSettings = MongoSettings()
    schedular_settings: SchedularSettings = SchedularSettings()
    aws_settings: AWSSettings = AWSSettings()
    https_cert_api_settings: HttpsCertificateApiSettings = HttpsCertificateApiSettings()
    sentry_settings: SentrySettings = SentrySettings()
    temporal_settings: TemporalSettings = TemporalSettings()

    # All your additional application configuration should go either here or in
    # separate file in this submodule.

    class Config:
        """Config sub class needed to customize BaseSettings settings."""

        case_sensitive = True


settings = Application()
