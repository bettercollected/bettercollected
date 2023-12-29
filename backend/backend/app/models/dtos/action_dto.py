import enum
from typing import List
from typing import Optional

from beanie import PydanticObjectId
from common.models.standard_form import Trigger
from fastapi_camelcase import CamelModel
from pydantic import BaseModel

from backend.app.schemas.action_document import ParameterValue, ActionSettings


class ActionDto(CamelModel):
    action_code: Optional[str]
    parameters: Optional[List[ParameterValue]]
    secrets: Optional[List[ParameterValue]]
    name: str
    title: Optional[str]
    description: Optional[str]


class ActionResponse(ActionDto, CamelModel):
    id: PydanticObjectId
    settings: Optional[ActionSettings] = None
    workspace_id: Optional[PydanticObjectId]


class AddActionToFormDto(BaseModel):
    action_id: PydanticObjectId
    trigger: Trigger = Trigger.on_submit
    parameters: Optional[List[ParameterValue]]
    secrets: Optional[List[ParameterValue]]


class ActionUpdateType(str, enum.Enum):
    ENABLE = "enable"
    DISABLE = "disable"


class UpdateActionInFormDto(CamelModel):
    action_id: PydanticObjectId
    update_type: ActionUpdateType
    trigger: Trigger = Trigger.on_submit
