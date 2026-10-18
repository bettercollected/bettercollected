from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class StripeSettings(StoreBackedSettings):
    product_id: Optional[str] = ""
    secret: Optional[str] = ""
    webhook_secret: Optional[str] = ""
    cancel_url: Optional[str] = ""
    success_url: Optional[str] = ""
    return_url: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="STRIPE_")
