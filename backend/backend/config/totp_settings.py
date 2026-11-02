"""The authenticator-app switch (``TOTP_ENABLED``).

Off (the default): the feature is invisible and inert. Nobody is asked for a
second factor at sign-in (not even an enrolled user), no workspace policy is
enforced, and the enrol, confirm and verify routes answer 422 ``totp_off``.
Stored factors stay as they are. On: staff can add an authenticator app to
their account (docs/totp.md).
"""

from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class TotpSettings(StoreBackedSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="TOTP_")
