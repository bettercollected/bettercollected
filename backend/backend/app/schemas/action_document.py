import datetime as dt
from typing import Optional, List

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from common.models.standard_form import ParameterValue
from pydantic import BaseModel, Field

from backend.app.handlers.database import entity


class BaseAction(BaseModel):
    name: str
    parameters: Optional[List[ParameterValue]]
    action_code: Optional[str] = Field(None)


@entity
class ActionDocument(BaseAction, MongoDocument):
    created_by: PydanticObjectId

    class Settings:
        name = "action"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
