import datetime as dt
from typing import Optional, Dict, List

from beanie import PydanticObjectId
from common.models.consent import ResponseRetentionType
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, Field, model_serializer


class WorkspaceRequestDto(BaseModel):
    """Model for creating or updating a workspace."""

    title: Optional[str] = None
    workspace_name: Optional[str] = None
    description: Optional[str] = None
    profile_image: Optional[str] = None
    banner_image: Optional[str] = None
    custom_domain: Optional[str] = None
    privacy_policy: Optional[str] = None
    terms_of_service: Optional[str] = None


class ParameterValue(BaseModel):
    name: Optional[str] = Field(None)
    value: Optional[str] = Field(None)
    required: Optional[bool] = Field(False)


class WorkspaceRequestWithActionDto(WorkspaceRequestDto):
    id: Optional[PydanticObjectId] = None
    parameters: Optional[Dict[str, Optional[List[ParameterValue]]]] = None
    secrets: Optional[Dict[str, Optional[List[ParameterValue]]]] = None


class WorkspaceRequestDtoCamel(WorkspaceRequestDto, CamelModel):
    pass


class Workspace(WorkspaceRequestDto):
    """Model for storing information about a workspace."""

    created_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None
    is_pro: Optional[bool] = None


class WorkspaceFormSettings(BaseModel):
    """Model for storing the form settings of a workspace."""

    pinned: Optional[bool] = False
    embed_url: Optional[str] = None
    custom_url: Optional[str] = None
    private: Optional[bool] = False
    hidden: Optional[bool] = False
    response_data_owner_field: Optional[str] = None
    provider: Optional[str] = None
    privacy_policy_url: Optional[str] = None
    response_expiration: Optional[str] = None
    response_expiration_type: Optional[ResponseRetentionType] = None
    disable_branding: Optional[bool] = None
    form_close_date: Optional[dt.datetime | str] = None
    require_verified_identity: Optional[bool] = None
    show_submission_number: Optional[bool] = None
    allow_editing_response: Optional[bool] = None
    show_original_form: Optional[bool] = None


class WorkspaceResponseDto(WorkspaceRequestDto, CamelModel):
    """Model for returning information about a workspace."""

    id: Optional[PydanticObjectId] = None
    owner_id: Optional[str] = None
    dashboard_access: Optional[bool] = None
    disabled: Optional[bool] = None
    default: Optional[bool] = None
    is_pro: Optional[bool] = False
    privacy_policy: Optional[str] = None
    terms_of_service: Optional[str] = None
    custom_domain_verified: Optional[bool] = False

