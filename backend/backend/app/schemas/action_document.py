import datetime as dt
from typing import Optional, List

import pymongo
from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from common.models.standard_form import ParameterValue
from pydantic import BaseModel, Field
from pymongo import IndexModel

from backend.app.handlers.database import entity


class BaseAction(BaseModel):
    name: str
    parameters: Optional[List[ParameterValue]]
    secrets: Optional[List[ParameterValue]]
    action_code: Optional[str] = Field(None)


class ActionSettings(BaseModel):
    is_public: bool = False


@entity
class ActionDocument(BaseAction, MongoDocument):
    created_by: PydanticObjectId
    workspace_id: PydanticObjectId
    settings: Optional[ActionSettings] = None

    class Settings:
        name = "action"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
        indexes = [
            IndexModel(
                [("workspace_id", pymongo.DESCENDING), ("action_name", pymongo.DESCENDING)],
                unique=True,
            )
        ]
