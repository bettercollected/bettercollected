from typing import List, Optional
import datetime as dt

from beanie import PydanticObjectId
from pydantic import BaseModel


class WorkspaceRequestDto(BaseModel):
    title: Optional[str]
    workspaceName: Optional[str]
    description: Optional[str]
    ownerId: Optional[PydanticObjectId]
    profileImage: Optional[str]
    bannerImage: Optional[str]
    customDomain: Optional[str]


class Workspace(WorkspaceRequestDto):
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]


class WorkspaceFormSettings(BaseModel):
    customUrl: Optional[str]
    responseDataOwnerField: Optional[str]
    pinned: bool = False
    roles: List[str] = []


class WorkspaceResponseDto(WorkspaceRequestDto):
    id: Optional[PydanticObjectId]


class WorkspaceFormPatch(BaseModel):
    form_id: str
    pinned: Optional[bool] = False
