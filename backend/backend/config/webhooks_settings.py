"""The webhooks switch (``WEBHOOKS_ENABLED``).

Off (the default): creating or enabling a webhook answers 422
``webhooks_off``, no submission queues a delivery, no delivery is sent and the
respondent's privacy panel names no destination; saved webhooks and the
delivery log stay as they are. On: a form's admins can send the answers of
chosen questions to an https address of their own (docs/webhooks.md).
"""

from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class WebhooksSettings(StoreBackedSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="WEBHOOKS_")
