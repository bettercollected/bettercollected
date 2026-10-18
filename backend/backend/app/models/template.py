from typing import Optional, List

from beanie import PydanticObjectId
from common.models.standard_form import (
    LOGO_ALT_MAX_LENGTH,
    LogoPosition,
    StandardFormField,
    Theme,
    WelcomePageField,
    EndingPages,
)
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, Field

from backend.app.models.dtos.response_dtos import StandardFormFieldCamelModel
from backend.app.models.enum.template import TemplateCategory


class StandardTemplateSetting(BaseModel):
    is_public: Optional[bool] = False
    # The language the template's questions are written in (a form's
    # settings.language), passed on to the forms made from it.
    language: Optional[str] = None


class StandardTemplateSettingsCamelModel(StandardTemplateSetting, CamelModel):
    pass


class StandardFormTemplate(BaseModel):
    id: Optional[PydanticObjectId] = None
    builder_version: Optional[str] = None
    workspace_id: Optional[PydanticObjectId] = None
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    logo_position: Optional[LogoPosition] = None
    logo_alt: Optional[str] = Field(None, max_length=LOGO_ALT_MAX_LENGTH)
    use_workspace_logo: Optional[bool] = None
    cover_image: Optional[str] = None
    category: Optional[TemplateCategory] = None
    button_text: Optional[str] = None
    fields: Optional[List[StandardFormField]] = None
    settings: Optional[StandardTemplateSetting] = StandardTemplateSetting()
    created_by: Optional[str] = None
    imported_from: Optional[PydanticObjectId] = None
    preview_image: Optional[str] = None
    theme: Optional[Theme] = None
    welcome_page: Optional[WelcomePageField] = None
    thankyou_page: Optional[EndingPages] = None


class StandardFormTemplateResponse(StandardFormTemplate):
    imported_from: Optional[str] = None
    fields: Optional[List[StandardFormFieldCamelModel]] = None


class StandardFormTemplateResponseCamelModel(CamelModel, StandardFormTemplateResponse):
    settings: StandardTemplateSettingsCamelModel = StandardTemplateSettingsCamelModel()


class StandardFormTemplateCamelModel(CamelModel, StandardFormTemplate):
    settings: StandardTemplateSettingsCamelModel = StandardTemplateSettingsCamelModel()
