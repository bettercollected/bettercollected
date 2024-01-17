from pydantic import BaseSettings

from backend.version import __version__


class ApiSettings(BaseSettings):
    ENVIRONMENT: str = "local"
    TITLE: str = "[BetterCollected] Forms Integrator Backend API"
    DESCRIPTION: str = "Rest endpoints for better-collected forms integrator API"
    VERSION: str = __version__
    ROOT_PATH: str = "/api/v1"
    HOST: str = ""
    ALLOWED_COLLABORATORS = 10
    ALLOWED_WORKSPACES = 5
    ENABLE_FORM_CREATION = False
    ENABLE_EXPORT_CSV: bool = False
    CLIENT_URL = "http://localhost:3000"
    ENABLE_GOOGLE_PICKER_API: bool = False
    ENABLE_REDEEM_CODE: bool = False

    class Config:
        env_prefix = "API_"
