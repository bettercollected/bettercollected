from beanie import PydanticObjectId
from pydantic import BaseSettings


class TemplateSettings(BaseSettings):
    PREDEFINED_WORKSPACE_ID: PydanticObjectId = None

    class Config:
        env_prefix = "TEMPLATE_"
