from pydantic_settings import SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class MongoSettings(StoreBackedSettings):
    """The 4.0 Mongo database, read only by the import (``python -m
    googleform.migrate``) and the startup check for data that was never
    imported (``googleform.db.import_guard``); the service itself is served from
    Postgres only. Store backed, as the backend's and auth's: a ``MONGO_URI``
    held in the settings store reaches the check."""

    DB: str = "bettercollected_googleform"
    URI: str = "mongodb://localhost"

    model_config = SettingsConfigDict(case_sensitive=True, env_prefix="MONGO_")
