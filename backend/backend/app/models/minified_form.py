import datetime as dt
from typing import Optional, List

from fastapi_camelcase import CamelModel

from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.models.dtos.workspace_member_dto import FormImporterDetails
from backend.app.models.response_dtos import (
    WorkspaceFormSettingsCamelModal,
    StandardFormFieldCamelModel,
)


class MinifiedForm(CamelModel):
    form_id: Optional[str]
    form_logo: Optional[str]
    form_cover: Optional[str]
    title: Optional[str]
    description: Optional[str]
    type: Optional[str]
    settings: Optional[WorkspaceFormSettingsCamelModal]
    created_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]
    responses: Optional[int]
    deletion_requests: Optional[int]
    groups: Optional[List[ResponderGroupDto]]
    imported_by: Optional[str]
    importer_details: Optional[FormImporterDetails]
    fields: Optional[List[StandardFormFieldCamelModel]]
    button_text: Optional[str]
