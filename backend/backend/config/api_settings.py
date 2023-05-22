from backend.version import __version__

from pydantic import BaseSettings


class ApiSettings(BaseSettings):
    TITLE: str = "[BetterCollected] Forms Integrator Backend API"
    DESCRIPTION: str = "Rest endpoints for better-collected forms integrator API"
    VERSION: str = __version__
    ROOT_PATH: str = "/api/v1"
    HOST: str = ""
    ALLOWED_COLLABORATORS = 10
    ALLOWED_WORKSPACES = 3

    class Config:
        env_prefix = "API_"
