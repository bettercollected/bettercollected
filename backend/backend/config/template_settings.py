from typing import Optional

from beanie import PydanticObjectId
from pydantic_settings import BaseSettings, SettingsConfigDict


class DefaultResourcesWorkspaceSettings(BaseSettings):
    WORKSPACE_ID: Optional[PydanticObjectId] = None
    SHOW_TEMPLATES: bool = False
    # Auto-seed the flow-native template gallery (scripts/seed_flow_templates.py)
    # on every app startup. Idempotent (skips templates that already exist) and
    # a no-op if WORKSPACE_ID is unset, so it's safe to leave on everywhere.
    SEED_FLOW_TEMPLATES: bool = True

    model_config = SettingsConfigDict(env_prefix='DEFAULT_')
