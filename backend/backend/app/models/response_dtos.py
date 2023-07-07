from typing import Optional

from fastapi_camelcase import CamelModel

from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDocument,
)
from common.models.standard_form import (
    StandardForm,
)


class WorkspaceFormSettingsCamelModal(WorkspaceFormSettings, CamelModel):
    pass


class StandardFormCamelModel(StandardForm, CamelModel):
    settings: Optional[WorkspaceFormSettingsCamelModal]
    responses: Optional[int] = 0


class StandardFormResponseCamelModel(FormResponseDocument, CamelModel):
    form_title: Optional[str]
    status: Optional[str]
    form_imported_by: Optional[str]
    deletion_status: Optional[DeletionRequestStatus]


class WorkspaceFormPatchResponse(CamelModel):
    settings: WorkspaceFormSettingsCamelModal
