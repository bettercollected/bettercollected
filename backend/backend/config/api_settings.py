from typing import Optional

from pydantic_settings import BaseSettings

from backend.version import __version__


class ApiSettings(BaseSettings):
    ENVIRONMENT: Optional[str] = "local"
    TITLE: Optional[str] = "[BetterCollected] Forms Integrator Backend API"
    DESCRIPTION: Optional[
        str
    ] = "Rest endpoints for better-collected forms integrator API"
    VERSION: Optional[str] = __version__
    ROOT_PATH: Optional[str] = "/api/v1"
    HOST: Optional[str] = ""
    ALLOWED_COLLABORATORS: Optional[int] = 10
    ALLOWED_WORKSPACES: Optional[int] = 5
    ENABLE_FORM_CREATION: Optional[bool] = False
    ENABLE_EXPORT_CSV: Optional[bool] = False
    CLIENT_URL: Optional[str] = "http://localhost:3000"
    ENABLE_GOOGLE_PICKER_API: Optional[bool] = False

    class Config:
        env_prefix = "API_"
