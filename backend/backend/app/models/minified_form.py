import datetime as dt
from typing import Dict, Optional, List

from fastapi_camelcase import CamelModel

from backend.app.models.response_dtos import WorkspaceFormSettingsCamelModal
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
    importer_details: Optional[Dict]
    fields: Optional[List[StandardFormField]]
