from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    AES_HEX_KEY: str = ""
    JWT_SECRET: str = ""
    # Access tokens are checked without a database read, so this is how long
    # a revoked session (logout everywhere, deleted account) keeps working.
    ACCESS_TOKEN_EXPIRY_IN_MINUTES: int = 15
    # Sliding: each explicit refresh extends the session by this much.
    REFRESH_TOKEN_EXPIRY_IN_DAYS: int = 30
    # How long the refresh token a rotation replaced is still accepted (tabs
    # and requests racing the rotation); after that, presenting it is treated
    # as theft and revokes the session.
    REFRESH_REUSE_GRACE_SECONDS: int = 60

    BASE_URL: str = "http://localhost:8001/api/v1"
    # Shared with the auth service (same AUTH_INTERNAL_NOTIFY_KEY): proves a
    # request comes from this backend. The name predates it, but the auth
    # service now refuses every API call without it (sign-in, session status,
    # users, billing, notifications), not only notification mails; sent via
    # backend.app.services.internal_auth.auth_service_headers.
    INTERNAL_NOTIFY_KEY: str = ""
    CALLBACK_URI: str = f"{BASE_URL}/auth/callback"

    model_config = SettingsConfigDict(env_prefix="AUTH_")
