from pydantic import BaseSettings


class AuthSettings(BaseSettings):
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRY_IN_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRY_IN_DAYS: int = 30

    AUTH_BASE_URL: str = "http://localhost:8001"
    AUTH_CALLBACK_URI: str = f"{AUTH_BASE_URL}/auth/auth_callback"

    class Config:
        env_prefix = "AUTH_"
