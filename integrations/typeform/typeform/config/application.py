"""Application configuration - FastAPI."""
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseSettings

from typeform.config.apm_settings import APMSettings
from typeform.config.database import MongoSettings
from typeform.config.sentry_setting import SentrySettings
from typeform.version import __version__

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

    Environment variables:
        * FASTAPI_DEBUG
        * FASTAPI_PROJECT_NAME
        * FASTAPI_VERSION
        * FASTAPI_DOCS_URL
        * FASTAPI_USE_REDIS

    Attributes:
        DEBUG (bool): FastAPI logging level. You should disable this for
            production.
        PROJECT_NAME (str): FastAPI project name.
        VERSION (str): Application version.
        DOCS_URL (str): Path where swagger ui will be served at.
        USE_REDIS (bool): Whether or not to use Redis.

    """

    DEBUG: bool = True
    PROJECT_NAME: str = "typeform"
    VERSION: str = __version__

    API_ROOT_PATH: str = "/api/v1"
    API_ENVIRONMENT: str = "local"
    API_VERSION: str = "1.0.0"
    DOCS_URL: str = "/docs"
    AUTH_SERVER_URL: str = "http://auth:8080/api/v1"

    AUTH_JWT_SECRET: str

    apm_settings: APMSettings = APMSettings()
    mongo_settings: MongoSettings = MongoSettings()
    sentry_settings: SentrySettings = SentrySettings()

    TYPEFORM_SCOPE = "offline+accounts:read+forms:read+responses:read"
    TYPEFORM_CLIENT_ID = ""
    TYPEFORM_CLIENT_SECRET = ""
    TYPEFORM_REDIRECT_URI = ""
    TYPEFORM_API_URI = "https://api.typeform.com"
    TYPEFORM_AUTH_URI = "https://api.typeform.com/oauth/authorize?state={state}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
    TYPEFORM_TOKEN_URI = "https://api.typeform.com/oauth/token"

    class Config:
        case_sensitive = True


settings = Application()
