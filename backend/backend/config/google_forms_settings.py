"""The Google Forms import switch (``GOOGLE_FORMS_IMPORT``).

``on`` (the default for self-hosted installs): imports, re-syncs and the
Google connection work as before. ``readonly``: imported forms and their
responses stay readable here, but nothing is processed with Google any more
(no new import, no re-sync, no new responses, no token refresh, no call to
Google). ``off``: the Google Forms endpoints answer 410 and nothing calls the
Google Forms service at all. The Google Forms service reads the same key and
refuses the same work on its side.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class GoogleFormsSettings(StoreBackedSettings):
    IMPORT: Literal["on", "readonly", "off"] = "on"

    @field_validator("IMPORT", mode="before")
    @classmethod
    def _normalise(cls, value):
        # an unknown value refuses to start rather than guessing a mode
        return value.strip().lower() if isinstance(value, str) else value

    model_config = SettingsConfigDict(env_prefix="GOOGLE_FORMS_")
