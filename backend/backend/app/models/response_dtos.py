from typing import Optional

from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.standard_form_response import FormResponseDocument

from common.models.standard_form import (
    StandardForm,
)

from fastapi_camelcase import CamelModel


class WorkspaceFormSettingsCamelModal(WorkspaceFormSettings, CamelModel):
    pass


class StandardFormCamelModel(StandardForm, CamelModel):
    settings: Optional[WorkspaceFormSettingsCamelModal]


class StandardFormResponseCamelModel(FormResponseDocument, CamelModel):
    form_title: Optional[str]
    deletion_status: Optional[str]


class WorkspaceFormPatchResponse(CamelModel):
    settings: WorkspaceFormSettingsCamelModal
