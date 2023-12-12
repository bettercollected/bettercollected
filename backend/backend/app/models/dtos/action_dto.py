from typing import Optional

from beanie import PydanticObjectId
from black import List
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
