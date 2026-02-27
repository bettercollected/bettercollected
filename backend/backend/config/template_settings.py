from beanie import PydanticObjectId
from pydantic_settings import BaseSettings, SettingsConfigDict


class DefaultResourcesWorkspaceSettings(BaseSettings):
    WORKSPACE_ID: PydanticObjectId = None
    SHOW_TEMPLATES: bool = False

    model_config = SettingsConfigDict(env_prefix='DEFAULT_')
