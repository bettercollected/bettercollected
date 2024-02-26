import datetime as dt
from typing import Optional

from beanie import PydanticObjectId
from common.models.consent import ResponseRetentionType
from fastapi_camelcase import CamelModel
from pydantic import BaseModel


class WorkspaceRequestDto(BaseModel):
    """Model for creating or updating a workspace."""

    title: Optional[str]
    workspace_name: Optional[str]
    description: Optional[str]
    profile_image: Optional[str]
    banner_image: Optional[str]
    custom_domain: Optional[str]
    privacy_policy: Optional[str]
    terms_of_service: Optional[str]


class WorkspaceRequestDtoCamel(WorkspaceRequestDto, CamelModel):
    pass


class Workspace(WorkspaceRequestDto):
    """Model for storing information about a workspace."""

    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    is_pro: Optional[bool]


class WorkspaceFormSettings(BaseModel):
    """Model for storing the form settings of a workspace."""

    pinned: Optional[bool] = False
    embed_url: Optional[str]
    custom_url: Optional[str]
    private: Optional[bool] = False
    hidden: Optional[bool] = False
    response_data_owner_field: Optional[str]
    provider: Optional[str]
    privacy_policy_url: Optional[str]
    response_expiration: Optional[str]
    response_expiration_type: Optional[ResponseRetentionType]
    disable_branding: Optional[bool]
    form_close_date: Optional[dt.datetime | str]
    require_verified_identity: Optional[bool]
    show_submission_number: Optional[bool]
    allow_editing_response: Optional[bool]


class WorkspaceResponseDto(WorkspaceRequestDto, CamelModel):
    """Model for returning information about a workspace."""

    id: Optional[PydanticObjectId]
    owner_id: Optional[str]
    dashboard_access: Optional[bool]
    disabled: Optional[bool]
    default: Optional[bool]
    is_pro: Optional[bool] = False
    privacy_policy: Optional[str]
    terms_of_service: Optional[str]
