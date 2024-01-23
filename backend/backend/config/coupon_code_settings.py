from pydantic import BaseSettings


class CouponCodeSettings(BaseSettings):
    ENABLED: bool = False
    EXPIRY_IN_DAYS: int = 60

    class Config:
        env_prefix = "COUPON_"
