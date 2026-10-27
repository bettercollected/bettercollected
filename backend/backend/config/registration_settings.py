"""The registration switch (``OPEN_FORMULIEREN_REGISTRATION``).

``off`` (the default): the registration endpoints answer 410, no submission
queues a delivery, no delivery is sent and the respondent's form carries no
destination; saved services, form settings and delivery records stay as they
are. ``on``: registration of submissions in a workspace's case system works
(docs/open-formulieren-registration.md).
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class RegistrationSettings(StoreBackedSettings):
    REGISTRATION: Literal["on", "off"] = "off"

    @field_validator("REGISTRATION", mode="before")
    @classmethod
    def _normalise(cls, value):
        # an unknown value refuses to start rather than guessing a mode
        return value.strip().lower() if isinstance(value, str) else value

    model_config = SettingsConfigDict(env_prefix="OPEN_FORMULIEREN_")
