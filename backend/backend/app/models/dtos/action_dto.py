from typing import Optional

from beanie import PydanticObjectId
from black import List
from fastapi_camelcase import CamelModel

from backend.app.schemas.action_document import ParameterValue


class ActionDto(CamelModel):
    action_code: str
    parameters: Optional[List[ParameterValue]]
    name: str


class ActionResponse(ActionDto, CamelModel):
    id: PydanticObjectId
