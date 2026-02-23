from pydantic_settings import BaseSettings, SettingsConfigDict


class CouponCodeSettings(BaseSettings):
    ENABLED: bool = False
    EXPIRY_IN_DAYS: int = 60

    model_config = SettingsConfigDict(env_prefix='COUPON_')
