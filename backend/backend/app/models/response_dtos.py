from typing import Optional

from fastapi_camelcase import CamelModel

from backend.app.models.workspace import WorkspaceFormSettings
from common.models.standard_form import StandardForm, StandardFormResponse, StandardFormSettings


class WorkspaceFormSettingsCamelModal(WorkspaceFormSettings, CamelModel):
    pass


class StandardFormCamelModel(StandardForm, CamelModel):
    settings: Optional[WorkspaceFormSettingsCamelModal]


class StandardFormResponseCamelModel(StandardFormResponse, CamelModel):
    form_title: Optional[str]
