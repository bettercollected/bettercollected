import datetime as dt
import re
from typing import Optional, Dict, List

from beanie import PydanticObjectId
from common.models.consent import ResponseRetentionType
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, Field, field_validator, model_serializer


HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


class WorkspaceThemeBackgroundDto(BaseModel):
    """Optional page-ground decoration for a saved theme.

    camelCase field names on purpose — the webapp sends the theme JSON
    verbatim (see common.models.standard_form.ThemeBackground).
    """

    type: str
    gradientFrom: Optional[str] = None
    gradientTo: Optional[str] = None
    gradientAngle: Optional[int] = None
    pattern: Optional[str] = None
    imageUrl: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in ("color", "gradient", "pattern", "image"):
            raise ValueError("Background type must be color, gradient, pattern or image.")
        return v

    @field_validator("gradientFrom", "gradientTo")
    @classmethod
    def _hex_stop(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not HEX_COLOUR.fullmatch(v):
            raise ValueError("Gradient colours must be 6-digit hex, e.g. #2456CC")
        return v

    @field_validator("gradientAngle")
    @classmethod
    def _sane_angle(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 0 <= v <= 360:
            raise ValueError("Gradient angle must be between 0 and 360.")
        return v

    @field_validator("pattern")
    @classmethod
    def _known_pattern(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("dots", "grid", "stripes"):
            raise ValueError("Pattern must be dots, grid or stripes.")
        return v

    @field_validator("imageUrl")
    @classmethod
    def _sane_image_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if len(v) > 2048:
            raise ValueError("Image URL must be 2048 characters or fewer.")
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("Image URL must start with http:// or https://")
        return v


class WorkspaceThemeDto(BaseModel):
    """A custom form theme saved at the workspace level.

    Mirrors the webapp's FormTheme roles (webapp/src/constants/theme.ts):
    primary = question/answer text, secondary = button fills, tertiary = input
    borders, accent = page background — optionally decorated by `background`.
    """

    title: str
    primary: str
    secondary: str
    tertiary: str
    accent: str
    background: Optional[WorkspaceThemeBackgroundDto] = None
    style: Optional[str] = None

    @field_validator("style")
    @classmethod
    def _known_style(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("classic", "sheet", "studio"):
            raise ValueError("Style must be classic, sheet or studio.")
        return v

    @field_validator("title")
    @classmethod
    def _sane_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Theme name cannot be empty.")
        if len(v) > 40:
            raise ValueError("Theme name must be 40 characters or fewer.")
        return v

    @field_validator("primary", "secondary", "tertiary", "accent")
    @classmethod
    def _hex_colour(cls, v: str) -> str:
        if not HEX_COLOUR.fullmatch(v):
            raise ValueError("Colours must be 6-digit hex, e.g. #2456CC")
        return v


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
    # Saved custom form themes ("brand kit" palettes). Optional and additive —
    # existing workspace documents simply have none.
    custom_themes: Optional[List[WorkspaceThemeDto]] = None


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
    # Trust layer content (Design-Language §4): why the data is collected and
    # how long it's kept, in the creator's plain words. Shown to responders on
    # every step of the form.
    purpose: Optional[str] = None
    retention_text: Optional[str] = None
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

