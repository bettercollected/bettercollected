from typing import List, Optional
import datetime as dt

from beanie import PydanticObjectId
from pydantic import BaseModel


class WorkspaceRequestDto(BaseModel):
    """Model for creating or updating a workspace."""

    title: Optional[str]
    workspaceName: Optional[str]
    description: Optional[str]
    ownerId: Optional[PydanticObjectId]
    profileImage: Optional[str]
    bannerImage: Optional[str]
    customDomain: Optional[str]


class Workspace(WorkspaceRequestDto):
    """Model for storing information about a workspace."""

    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]


class WorkspaceFormSettings(BaseModel):
    """Model for storing the form settings of a workspace."""

    customUrl: Optional[str]
    responseDataOwnerField: Optional[str]
    pinned: bool = False
    roles: List[str] = []


class WorkspaceResponseDto(WorkspaceRequestDto):
    """Model for returning information about a workspace."""

    id: Optional[PydanticObjectId]


class WorkspaceFormPatch(BaseModel):
    """Model for patching the form settings of a workspace."""

    form_id: str
    pinned: Optional[bool] = False
