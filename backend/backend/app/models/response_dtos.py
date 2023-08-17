from typing import Optional, Dict, List

from fastapi_camelcase import CamelModel

from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDocument,
)
from common.models.standard_form import (
    StandardForm,
    StandardFormFieldType,
    FormBuilderTagTypes,
    StandardFieldAttachment,
)


class WorkspaceFormSettingsCamelModal(WorkspaceFormSettings, CamelModel):
    pass


class StandardFormCamelModel(StandardForm, CamelModel):
    settings: Optional[WorkspaceFormSettingsCamelModal]
    responses: Optional[int] = 0


class StandardChoice(CamelModel):
    id: Optional[str]
    ref: Optional[str]
    value: Optional[str]
    label: Optional[str]
    attachment: Optional[StandardFieldAttachment]


class StandardFieldValidationsCamelModal(CamelModel):
    required: Optional[bool]
    max_length: Optional[int]
    min_length: Optional[int]
    min_value: Optional[float]
    max_value: Optional[float]
    min_choices: Optional[int]
    max_choices: Optional[int]
    regex: Optional[str]


class StandardFieldPropertyCamelModel(CamelModel):
    hidden: Optional[bool]
    description: Optional[str]
    choices: Optional[List[StandardChoice]]
    fields: Optional[List["StandardFormFieldCamelModel"]]
    allow_multiple_selection: Optional[bool]
    allow_other_choice: Optional[bool]
    hide_marks: Optional[bool]
    button_text: Optional[str]
    placeholder: Optional[str]
    steps: Optional[int]
    start_form: Optional[int]
    rating_shape: Optional[str]
    labels: Optional[Dict[str, str]]
    date_format: Optional[str]
    updateId: Optional[str]


class StandardFormFieldCamelModel(CamelModel):
    id: Optional[str]
    ref: Optional[str]
    title: Optional[str]
    description: Optional[str]
    value: Optional[str]
    type: Optional[StandardFormFieldType]
    tag: Optional[FormBuilderTagTypes]
    properties: Optional[StandardFieldPropertyCamelModel]
    validations: Optional[StandardFieldValidationsCamelModal]
    attachment: Optional[StandardFieldAttachment] = None


StandardFieldPropertyCamelModel.update_forward_refs()


class StandardFormResponseCamelModel(FormResponseDocument, CamelModel):
    form_title: Optional[str]
    status: Optional[str]
    form_imported_by: Optional[str]
    deletion_status: Optional[DeletionRequestStatus]


class WorkspaceFormPatchResponse(CamelModel):
    settings: WorkspaceFormSettingsCamelModal
