from enum import Enum
from typing import Optional, List

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from pydantic import BaseModel, Field


class ParameterValue(BaseModel):
    name: str = Field(None)
    value: str = Field(None)


class BaseAction(BaseModel):
    name: str
    parameters: Optional[List[ParameterValue]]
    action_code: Optional[str] = Field(None)


class Trigger(str, Enum):
    # This trigger is run when form response is submitted
    on_submit = "on_submit"
    # This trigger is run when form is opened
    on_open = "on_open"


class ActionDocument(BaseAction, MongoDocument):
    created_by: PydanticObjectId

    class Settings:
        name = "action"
