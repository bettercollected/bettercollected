"""The Open Formulieren import switch (``OPEN_FORMULIEREN_IMPORT``).

``off`` (the default): the import endpoints answer 410 and the providers list
does not offer it. ``on``: a workspace member who may create forms can import
a form exported from Open Formulieren as a draft (docs/open-formulieren.md).
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class OpenFormulierenSettings(StoreBackedSettings):
    IMPORT: Literal["on", "off"] = "off"

    @field_validator("IMPORT", mode="before")
    @classmethod
    def _normalise(cls, value):
        # an unknown value refuses to start rather than guessing a mode
        return value.strip().lower() if isinstance(value, str) else value

    model_config = SettingsConfigDict(env_prefix="OPEN_FORMULIEREN_")
