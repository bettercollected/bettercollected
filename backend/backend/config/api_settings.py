from pydantic import BaseSettings
from backend.version import __version__


class ApiSettings(BaseSettings):
    TITLE: str = "[BetterCollected] Forms Integrator Backend API"
    DESCRIPTION: str = "Rest endpoints for better-collected forms integrator API"
    VERSION: str = __version__
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ROOT_PATH: str = "/api/v1"
    HOST: str = "http://localhost:8000"

    class Config:
        env_prefix = "API_"
