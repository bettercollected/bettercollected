"""Application configuration - FastAPI."""

import os
from pathlib import Path

from common.configs.shipped_secrets import require_secrets
from common.services.keyset_source import configured_key_ids
from common.settings.loader import ensure_poller, load_snapshot, set_keyset_key_ids
from common.settings.loader.pydantic_source import StoreBackedSettings
from dotenv import load_dotenv

from googleform.config.apm_settings import APMSettings
from googleform.config.database import MongoSettings
from googleform.config.sentry_setting import SentrySettings
from googleform.version import __version__

from pydantic_settings import BaseSettings

default_dot_env_path = (
    Path(os.path.abspath(os.path.dirname(__file__)))
    .parent.parent.absolute()
    .joinpath(".env")
)
load_dotenv(os.getenv("DOTENV_PATH", default_dot_env_path))

# Settings may come from the signed settings store (SETTINGS_STORE=off|auto|
# required; auto and unconfigured means environment and defaults only). One
# snapshot is read here, before the settings classes below are built.
load_snapshot(
    "google",
    required_env_keys=("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY"),
)



class Application(StoreBackedSettings):
    """Define application configuration model.

    Constructor will attempt to determine the values of any fields not passed
    as keyword arguments by reading from the environment. Default values will
    still be used if the matching environment variable is not set.

    Environment variables:
        * FASTAPI_DEBUG
        * FASTAPI_PROJECT_NAME
        * FASTAPI_VERSION
        * FASTAPI_DOCS_URL

    Attributes:
        DEBUG (bool): FastAPI debug mode (HTML tracebacks for unhandled
            errors). Off unless explicitly enabled; keep it off in production.
        PROJECT_NAME (str): FastAPI project name.
        VERSION (str): Application version.
        DOCS_URL (str): Path where swagger ui will be served at.

    """

    DEBUG: bool = False
    PROJECT_NAME: str = "googleform"
    VERSION: str = __version__

    API_ROOT_PATH: str = "/api/v1"
    # Interactive API docs and the OpenAPI document of this internal API.
    API_DOCS_ENABLED: bool = False
    API_VERSION: str = "1.0.0"
    API_ENVIRONMENT: str = "local"
    DOCS_URL: str = "/docs"

    AUTH_JWT_SECRET: str
    AUTH_SERVER_URL: str = "http://auth:8000/api/v1"
    # Shared with the backend and the auth service (same value everywhere):
    # the auth service refuses requests without it (X-Internal-Key).
    AUTH_INTERNAL_NOTIFY_KEY: str = ""
    AUTH_AES_HEX_KEY: str = ""

    GOOGLE_CLIENT_TYPE: str = "web"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_PROJECT_ID: str = ""
    GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_AUTH_PROVIDER_X509_CERT_URL: str = (
        "https://www.googleapis.com/oauth2/v1/certs"
    )
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URIS: str = ""
    GOOGLE_JAVASCRIPT_ORIGINS: str = ""
    GOOGLE_SCOPES: str = (
        "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/forms.body.readonly https://www.googleapis.com/auth/forms.responses.readonly"
    )
    GOOGLE_SHEET_SCOPE: str = (
        "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive"
    )
    GOOGLE_SHEET_REDIRECT_URL: str = (
        "http://localhost:3000/integrations/google/callback"
    )
    GOOGLE_API_SERVICE_NAME: str = "drive"
    GOOGLE_API_VERSION: str = "v2"
    GOOGLE_REVOKE_CREDENTIALS_URL: str = "https://oauth2.googleapis.com/revoke"
    MAX_THREAD_POOL_EXECUTORS: int = 150
    # on | readonly | off, read by the backend too (backend/config/
    # google_forms_settings.py). readonly and off refuse every Google Forms
    # route here (listing, import, token check and refresh, connecting an
    # account, handing out a stored credential); the Sheets routes and
    # deleting stored credentials stay.
    GOOGLE_FORMS_IMPORT: str = "on"

    apm_settings: APMSettings = APMSettings()
    mongo_settings: MongoSettings = MongoSettings()
    sentry_settings: SentrySettings = SentrySettings()

    # All your additional application configuration should go either here or in
    # separate file in this submodule.

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
# The heartbeat carries the fingerprint of the keyset this service holds (key ids
# only); the admin keyset tasks refuse to promote, re-encrypt or drop a key while
# a reporting consumer's fingerprint does not match the stored keyset.
set_keyset_key_ids(configured_key_ids)
ensure_poller()  # no-op when the store is off

# Tokens from the auth service are checked with AUTH_JWT_SECRET and Google
# credentials are encrypted with AUTH_AES_HEX_KEY: never run with either unset
# or set to a value published in the repository.
require_secrets(
    "the Google Forms integration",
    jwt_secrets={"AUTH_JWT_SECRET": settings.AUTH_JWT_SECRET},
    fernet_keys={"AUTH_AES_HEX_KEY": settings.AUTH_AES_HEX_KEY},
)
