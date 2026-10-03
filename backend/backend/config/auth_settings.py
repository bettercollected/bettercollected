from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    AES_HEX_KEY: str = ""
    JWT_SECRET: str = ""
    ACCESS_TOKEN_EXPIRY_IN_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRY_IN_DAYS: int = 30

    BASE_URL: str = "http://localhost:8001/api/v1"
    # Shared with the auth service (same AUTH_INTERNAL_NOTIFY_KEY): proves a
    # notification request comes from this backend, not from any user.
    INTERNAL_NOTIFY_KEY: str = ""
    CALLBACK_URI: str = f"{BASE_URL}/auth/callback"

    model_config = SettingsConfigDict(env_prefix="AUTH_")
