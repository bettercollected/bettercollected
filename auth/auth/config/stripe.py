from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class StripeSettings(BaseSettings):
    product_id: Optional[str] = ""
    secret: Optional[str] = ""
    webhook_secret: Optional[str] = ""
    cancel_url: Optional[str] = ""
    success_url: Optional[str] = ""
    return_url: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="STRIPE_")
