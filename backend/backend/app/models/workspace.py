from typing import List, Optional
import datetime as dt

from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel
from pydantic import BaseModel


class WorkspaceRequestDto(CamelModel):
    """Model for creating or updating a workspace."""

    title: Optional[str]
    workspace_name: Optional[str]
    description: Optional[str]
    owner_id: Optional[str]
    profile_image: Optional[str]
    banner_image: Optional[str]
    custom_domain: Optional[str]


class Workspace(WorkspaceRequestDto):
    """Model for storing information about a workspace."""

    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]


class WorkspaceFormSettings(CamelModel):
    """Model for storing the form settings of a workspace."""

    pinned: Optional[bool] = False
    custom_url: Optional[str]
    private: Optional[bool] = False
    response_data_owner_field: Optional[str]
    provider: Optional[str]


class WorkspaceResponseDto(WorkspaceRequestDto):
    """Model for returning information about a workspace."""

    id: Optional[PydanticObjectId]
