from pydantic import BaseSettings


class ApiSettings(BaseSettings):
    """
    A class for storing API settings.

    This class inherits from `BaseSettings` and defines various attributes
    for API settings, including the environment, organization name, title,
    description, version, allowed origins, and paths for the documentation,
    OpenAPI specification, and root path. It also defines settings for the
    host, JWT secret, and expiry times for access and refresh tokens. The
    `scheduler_time_in_seconds` attribute specifies the interval at which
    the scheduler should run.

    The `Config` inner class specifies that environment variables should be
    prefixed with "API_" when loading the settings.
    """

    environment: str = "development"
    organization_name: str = "Better Collected"
    title: str = "[BetterCollected] Google Forms Integrations API"
    description: str = (
        "Rest endpoints for better-collected google forms integrations API"
    )
    version: str = "1.0.0"
    allowed_origins: str = "http://localhost:3000"
    root_path: str = "/"
    docs_path: str = "/docs"
    redoc_path: str = "/redoc"
    openapi_path: str = "/openapi.json"
    host: str = "http://localhost:8000"
    root_path_in_servers = False
    key_prefix: str = "better_collected_"
    key_id_length: int = 35
    key_password_length: int = 20
    jwt_secret: str = ""
    access_token_expiry_minutes: int = 60
    refresh_token_expiry_days: int = 30
    client_redirect_uri = "https://bettercollected.com"
    scheduler_time_in_seconds = 30

    class Config:
        env_prefix = "API_"
