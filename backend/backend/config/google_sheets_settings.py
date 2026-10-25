"""Who runs the Google Sheets action's OAuth flow (``GOOGLE_SHEETS_OAUTH``).

``google_service`` (the default): the Google Forms service builds the
authorization URL with its own client, exchanges the code and creates the
spreadsheet, as before. ``backend``: the backend does all three itself
(services/google_sheets_oauth.py) with the Google sign-in client below and only
the ``drive.file`` scope; the Google Forms service is not called.

Switch to ``backend`` only after the redirect address (``GOOGLE_SHEET_REDIRECT_URL``)
is registered on the sign-in client and ``drive.file`` is on its consent
screen (docs/RUNNING_INTEGRATIONS.md).
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class GoogleSheetsSettings(StoreBackedSettings):
    SHEETS_OAUTH: Literal["backend", "google_service"] = "google_service"
    # The Google sign-in client, shared with the auth service.
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""
    AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    # The webapp's callback page, the same address the Google Forms service uses.
    SHEET_REDIRECT_URL: str = "http://localhost:3000/integrations/google/callback"

    @field_validator("SHEETS_OAUTH", mode="before")
    @classmethod
    def _normalise(cls, value):
        # an unknown value refuses to start rather than guessing a mode
        return value.strip().lower() if isinstance(value, str) else value

    model_config = SettingsConfigDict(env_prefix="GOOGLE_")
