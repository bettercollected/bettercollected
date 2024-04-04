from typing import Optional, List

from beanie import PydanticObjectId
from common.models.standard_form import (
    StandardFormField,
    Theme,
    WelcomePageField,
    ThankYouPageField,
)
from fastapi_camelcase import CamelModel
from pydantic import BaseModel

from backend.app.models.enum.template import TemplateCategory


class StandardTemplateSetting(BaseModel):
    is_public: Optional[bool] = False


class StandardTemplateSettingsCamelModel(StandardTemplateSetting, CamelModel):
    pass


class StandardFormTemplate(BaseModel):
    id: Optional[PydanticObjectId]
    builder_version: Optional[str]
    workspace_id: Optional[PydanticObjectId]
    type: Optional[str]
    title: Optional[str]
    description: Optional[str]
    logo: Optional[str]
    cover_image: Optional[str]
    category: Optional[TemplateCategory]
    button_text: Optional[str]
    fields: Optional[List[StandardFormField]]
    settings: Optional[StandardTemplateSetting] = StandardTemplateSetting()
    created_by: Optional[str]
    imported_from: Optional[PydanticObjectId]
    preview_image: Optional[str]
    theme: Optional[Theme]
    welcome_page: Optional[WelcomePageField]
    thankyou_page: Optional[List[ThankYouPageField]]


class StandardFormTemplateResponse(StandardFormTemplate):
    imported_from: Optional[str]


class StandardFormTemplateResponseCamelModel(CamelModel, StandardFormTemplateResponse):
    settings: StandardTemplateSettingsCamelModel = StandardTemplateSettingsCamelModel()


class StandardFormTemplateCamelModel(CamelModel, StandardFormTemplate):
    settings: StandardTemplateSettingsCamelModel = StandardTemplateSettingsCamelModel()
