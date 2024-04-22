import datetime as dt
from typing import Optional, List, Dict

from common.models.standard_form import (
    ParameterValue,
    Trigger,
    ActionState,
    WelcomePageField,
    ThankYouPageField,
)
from fastapi_camelcase import CamelModel

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.models.dtos.workspace_member_dto import FormImporterDetails
from backend.app.models.dtos.response_dtos import (
    WorkspaceFormSettingsCamelModal,
    StandardFormFieldCamelModel,
)

from common.models.standard_form import Theme


class FormDtoCamelModel(CamelModel):
    builder_version: Optional[str]
    form_id: Optional[str]
    imported_form_id: Optional[str]
    logo: Optional[str]
    cover_image: Optional[str]
    title: Optional[str]
    description: Optional[str]
    type: Optional[str]
    button_text: Optional[str]
    settings: Optional[WorkspaceFormSettingsCamelModal]
    is_published: Optional[bool]
    is_multi_page: Optional[bool]
    created_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]
    consent: Optional[List[ConsentCamelModel]]
    responses: Optional[int]
    deletion_requests: Optional[int]
    groups: Optional[List[ResponderGroupDto]]
    imported_by: Optional[str]
    importer_details: Optional[FormImporterDetails]
    fields: Optional[List[StandardFormFieldCamelModel]]
    version: Optional[str]
    updated_at: Optional[dt.datetime]
    actions: Optional[Dict[Trigger, List[ActionState]]]
    parameters: Optional[Dict[str, List[ParameterValue]]]
    secrets: Optional[Dict[str, List[ParameterValue]]]
    theme: Optional[Theme]
    welcome_page: Optional[WelcomePageField]
    thankyou_page: Optional[List[ThankYouPageField]]
