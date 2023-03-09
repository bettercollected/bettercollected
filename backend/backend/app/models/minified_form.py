from typing import Optional
import datetime as dt

from pydantic import BaseModel

from backend.app.models.response_dtos import WorkspaceFormSettingsCamelModal
from backend.app.models.workspace import WorkspaceFormSettings


class MinifiedForm(BaseModel):
    form_id: str
    title: Optional[str]
    description: Optional[str]
    type: Optional[str]
    settings: Optional[WorkspaceFormSettingsCamelModal]
    created_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]
