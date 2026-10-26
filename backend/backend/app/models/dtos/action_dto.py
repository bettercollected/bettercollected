import enum
from typing import List
from typing import Optional

from common.ids import RecordId
from common.models.standard_form import Trigger
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, Field, model_serializer

from backend.app.schemas.action_document import ParameterValue, ActionSettings


class ActionDto(CamelModel):
    action_code: Optional[str] = None
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    predefined: Optional[bool] = None
    url: Optional[str] = None


class ActionResponse(ActionDto, CamelModel):
    """An action as the API shows it: its code and secrets stay in the backend
    (the job input is built from the stored document, not from this)."""

    action_code: Optional[str] = Field(None, exclude=True)
    secrets: Optional[List[ParameterValue]] = Field(None, exclude=True)
    id: RecordId
    settings: Optional[ActionSettings] = None
    workspace_id: Optional[RecordId] = None


class AddActionToFormDto(BaseModel):
    action_id: RecordId
    trigger: Trigger = Trigger.on_submit
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None


class ActionUpdateType(str, enum.Enum):
    ENABLE = "enable"
    DISABLE = "disable"


class UpdateActionInFormDto(CamelModel):
    action_id: RecordId
    update_type: ActionUpdateType
    trigger: Trigger = Trigger.on_submit
