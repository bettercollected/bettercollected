import datetime as dt
from typing import Optional, List

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from common.models.standard_form import ParameterValue
from pydantic import BaseModel, Field

from backend.app.handlers.database import entity


class BaseAction(BaseModel):
    name: str
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None
    action_code: Optional[str] = Field(None)


class ActionSettings(BaseModel):
    is_public: bool = False


@entity
class ActionDocument(MongoDocument):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    action_code: str
    created_by: PydanticObjectId
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None
    type: Optional[str] = None
    predefined: Optional[bool] = None
    url: Optional[str] = None

    class Settings:
        name = "actions"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


@entity
class WorkspaceActionsDocument(MongoDocument):
    workspace_id: PydanticObjectId
    action_id: PydanticObjectId
    settings: Optional[ActionSettings] = ActionSettings()
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None

    class Settings:
        name = "workspace_actions"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
