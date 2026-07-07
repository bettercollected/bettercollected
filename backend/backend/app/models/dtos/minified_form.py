import datetime as dt
from typing import Optional, List, Dict

from common.models.standard_form import (
    ParameterValue,
    Trigger,
    ActionState,
    WelcomePageField,
    ThankYouPageField,
)
from common.models.standard_form import Theme
from fastapi_camelcase import CamelModel

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.dtos.response_dtos import (
    WorkspaceFormSettingsCamelModal,
    StandardFormFieldCamelModel,
)
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.models.dtos.workspace_member_dto import FormImporterDetails


class FormDtoCamelModel(CamelModel):
    builder_version: Optional[str] = None
    form_id: Optional[str] = None
    imported_form_id: Optional[str] = None
    logo: Optional[str] = None
    cover_image: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    button_text: Optional[str] = None
    settings: Optional[WorkspaceFormSettingsCamelModal] = None
    is_published: Optional[bool] = None
    is_multi_page: Optional[bool] = None
    created_at: Optional[dt.datetime] = None
    published_at: Optional[dt.datetime] = None
    consent: Optional[List[ConsentCamelModel]] = None
    responses: Optional[int] = None
    deletion_requests: Optional[int] = None
    groups: Optional[List[ResponderGroupDto]] = None
    imported_by: Optional[str] = None
    importer_details: Optional[FormImporterDetails] = None
    fields: Optional[List[StandardFormFieldCamelModel]] = None
    hidden_fields: Optional[List[str]] = None
    version: Optional[str | int] = None
    updated_at: Optional[dt.datetime] = None
    actions: Optional[Dict[Trigger, List[ActionState]]] = None
    parameters: Optional[Dict[str, List[ParameterValue]]] = None
    secrets: Optional[Dict[str, List[ParameterValue]]] = None
    row_titles: Optional[List[str]] = None
    column_titles: Optional[List[str]] = None
    tabular_value: Optional[List[List[str]]] = None

    theme: Optional[Theme] = None
    welcome_page: Optional[WelcomePageField] = None
    thankyou_page: Optional[List[ThankYouPageField]] = None
    unauthorized: Optional[bool] = None
