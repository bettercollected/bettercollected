from pydantic import BaseSettings


class AuthSettings(BaseSettings):
    AES_HEX_KEY: str
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRY_IN_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRY_IN_DAYS: int = 30

    AUTH_BASE_URL: str = "http://localhost:8001/api/v1"
    AUTH_CALLBACK_URI: str = f"{AUTH_BASE_URL}/auth/callback"

    class Config:
        env_prefix = "AUTH_"
