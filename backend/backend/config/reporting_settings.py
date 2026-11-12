"""The reporting switch (``REPORTING_ENABLED``).

Off (the default): every report route answers 422 ``reporting_off`` before any
permission is looked at, any row is read or any answer decrypted, and nothing
else changes: the responses list, the export, analytics and AI insights are the
same with the switch on or off. On: a member who may read a form's responses
and its analytics can ask for counts and averages computed from the answers.

Read from the environment only, deliberately, like ``FORM_ACCESS_ENABLED`` and
``FORM_PROMOTION_ENABLED``: it becomes a stored setting (tier T2) when it is
released.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportingSettings(BaseSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="REPORTING_")
