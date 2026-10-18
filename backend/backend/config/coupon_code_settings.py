from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class CouponCodeSettings(StoreBackedSettings):
    ENABLED: bool = False
    EXPIRY_IN_DAYS: int = 60

    model_config = SettingsConfigDict(env_prefix='COUPON_')
