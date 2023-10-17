from typing import Optional, List

from beanie import PydanticObjectId
from common.models.standard_form import StandardFormField
from fastapi_camelcase import CamelModel
from pydantic import BaseModel

from backend.app.models.enum.template import TemplateCategory


class StandardTemplateSetting(BaseModel):
    is_public: Optional[bool] = False


class StandardFormTemplate(BaseModel):
    id: Optional[PydanticObjectId]
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


class StandardFormTemplateCamelModel(CamelModel, StandardFormTemplate):
    pass
