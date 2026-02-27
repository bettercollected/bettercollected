from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.version import __version__


class ApiSettings(BaseSettings):
    ENVIRONMENT: str = "local"
    TITLE: str = "[BetterCollected] Forms Integrator Backend API"
    DESCRIPTION: str = "Rest endpoints for better-collected forms integrator API"
    VERSION: str = __version__
    ROOT_PATH: str = "/api/v1"
    HOST: str = ""
    DOMAIN: Optional[str] = ""
    ALLOWED_COLLABORATORS: int = 10
    ALLOWED_WORKSPACES: int = 5
    ENABLE_FORM_CREATION: bool = False
    ENABLE_EXPORT_CSV: bool = False
    CLIENT_URL: str = "http://localhost:3000"
    ENABLE_GOOGLE_PICKER_API: bool = False

    model_config = SettingsConfigDict(env_prefix="API_")
