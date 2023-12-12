from beanie import PydanticObjectId
from pydantic import BaseSettings


class DefaultResourcesWorkspaceSettings(BaseSettings):
    WORKSPACE_ID: PydanticObjectId = None
    SHOW_TEMPLATES: bool = False

    class Config:
        env_prefix = "DEFAULT_"
