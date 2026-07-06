from typing import Any, Optional, Dict, List

from common.models.standard_form import (
    StandardForm,
    StandardFormFieldType,
    FormBuilderTagTypes,
    StandardFieldAttachment,
    Condition,
    ConditionalActions,
    FieldLogic,
    FieldPosition,
    PageJump,
    LogicalOperator,
    LayoutType,
    Theme,
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
    is_published: Optional[bool] = None


class StandardFormCamelModel(StandardForm, CamelModel):
    model_config = {"extra": "allow"}
    settings: Optional[WorkspaceFormSettingsCamelModal] = None
    responses: Optional[int] = 0
    version: Optional[int] = None


class StandardChoice(CamelModel):
    id: Optional[str] = None
    ref: Optional[str] = None
    value: Optional[str] = None
    label: Optional[str] = None
    attachment: Optional[StandardFieldAttachment] = None


class StandardFieldValidationsCamelModal(CamelModel):
    required: Optional[bool] = None
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_choices: Optional[int] = None
    max_choices: Optional[int] = None
    regex: Optional[str] = None


class ConditionCamelModel(Condition, CamelModel):
    pass


class ConditionalActionsCamelModel(ConditionalActions, CamelModel):
    pass


class StandardFieldPropertyCamelModel(CamelModel):
    hidden: Optional[bool] = None
    description: Optional[str] = None
    choices: Optional[List[StandardChoice]] = None
    fields: Optional[List["StandardFormFieldCamelModel"]] = None
    allow_multiple_selection: Optional[bool] = None
    allow_other_choice: Optional[bool] = None
    hide_marks: Optional[bool] = None
    button_text: Optional[str] = None
    placeholder: Optional[str] = None
    steps: Optional[int] = None
    start_from: Optional[int] = None
    rating_shape: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    date_format: Optional[str] = None
    update_id: Optional[str] = None
    actions: Optional[List[ConditionalActionsCamelModel]] = None
    conditions: Optional[List[ConditionCamelModel]] = None
    logical_operator: Optional[LogicalOperator] = None
    logic: Optional[FieldLogic] = None
    jumps: Optional[List[PageJump]] = None
    position: Optional[FieldPosition] = None
    mentions: Optional[Dict[str, str]] = None
    theme: Optional[Theme] = None
    layout: Optional[LayoutType] = None
    row_titles: Optional[List[str]] = None
    column_titles: Optional[List[str]] = None
    tabular_value: Optional[List[List[str]]] = None


class StandardFormFieldCamelModel(CamelModel):
    id: Optional[str] = None
    ref: Optional[str] = None
    title: Optional[str | Dict[str, Any]] = None
    description: Optional[str] = None
    value: Optional[str] = None
    index: Optional[int] = None
    type: Optional[StandardFormFieldType] = None
    tag: Optional[FormBuilderTagTypes] = None
    properties: Optional[StandardFieldPropertyCamelModel] = None
    validations: Optional[StandardFieldValidationsCamelModal] = None
    attachment: Optional[StandardFieldAttachment] = None
    image_url: Optional[str] = None


StandardFieldPropertyCamelModel.model_rebuild()


class StandardFormResponseCamelModel(FormResponseDocument, CamelModel):
    form_title: Optional[str] = None
    status: Optional[str] = None
    form_imported_by: Optional[str] = None
    consent: Optional[List[ConsentResponseCamelModel]] = None
    deletion_status: Optional[DeletionRequestStatus] = None
    anonymize: Optional[bool] = None


class FormFileResponse(BaseModel):
    file_id: str
    field_id: str
    filename: str
    file: UploadFile


class WorkspaceFormPatchResponse(CamelModel):
    settings: WorkspaceFormSettingsCamelModal
