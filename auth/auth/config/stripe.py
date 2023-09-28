from pydantic import BaseSettings


class StripeSettings(BaseSettings):
    product_id: str = ""
    secret: str = ""
    webhook_secret: str = ""
    cancel_url: str = ""
    success_url: str = ""
    return_url: str = ""

    class Config:
        env_prefix = "STRIPE_"
