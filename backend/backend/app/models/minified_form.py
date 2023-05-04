import datetime as dt
from typing import Optional, List

from backend.app.models.response_dtos import WorkspaceFormSettingsCamelModal

from fastapi_camelcase import CamelModel

from common.models.standard_form import StandardFormField


class MinifiedForm(CamelModel):
    form_id: str
    title: Optional[str]
    description: Optional[str]
    type: Optional[str]
    settings: Optional[WorkspaceFormSettingsCamelModal]
    created_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]
    responses: Optional[int]
    deletion_requests: Optional[int]
    imported_by: Optional[str]
    importer_details: Optional[dict]
    fields: Optional[List[StandardFormField]]
