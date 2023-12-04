from typing import Optional, List

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from common.models.standard_form import ParameterValue
from pydantic import BaseModel, Field


class BaseAction(BaseModel):
    name: str
    parameters: Optional[List[ParameterValue]]
    action_code: Optional[str] = Field(None)


class ActionDocument(BaseAction, MongoDocument):
    created_by: PydanticObjectId

    class Settings:
        name = "action"
