from typing import Optional, Dict, List

from common.models.standard_form import (
    StandardForm,
    StandardFormFieldType,
    FormBuilderTagTypes,
    StandardFieldAttachment,
    Condition,
    ConditionalActions,
    LogicalOperator,
)
from fastapi import UploadFile
from fastapi_camelcase import CamelModel
from pydantic import BaseModel

from backend.app.models.dtos.consent import ConsentResponseCamelModel
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDocument,
)


class WorkspaceFormSettingsCamelModal(WorkspaceFormSettings, CamelModel):
    is_published: Optional[bool]
    pass


class StandardFormCamelModel(StandardForm, CamelModel):
    settings: Optional[WorkspaceFormSettingsCamelModal]
    responses: Optional[int] = 0
    version: Optional[int]


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


class ConditionCamelModel(Condition, CamelModel):
    pass


class ConditionalActionsCamelModel(ConditionalActions, CamelModel):
    pass


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
    update_id: Optional[str]
    actions: Optional[List[ConditionalActionsCamelModel]]
    conditions: Optional[List[ConditionCamelModel]]
    logical_operator: Optional[LogicalOperator]
    mentions: Optional[Dict[str, str]]


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
    consent: Optional[List[ConsentResponseCamelModel]]
    deletion_status: Optional[DeletionRequestStatus]
    anonymize: Optional[bool]


class FormFileResponse(BaseModel):
    file_id: str
    field_id: str
    filename: str
    file: UploadFile


class WorkspaceFormPatchResponse(CamelModel):
    settings: WorkspaceFormSettingsCamelModal
