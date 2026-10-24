import datetime as dt
from typing import Optional, List

from common.models.standard_form import ParameterValue
from common.records import Record, RecordId
from pydantic import BaseModel, Field


class BaseAction(BaseModel):
    name: str
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None
    action_code: Optional[str] = Field(None)


class ActionSettings(BaseModel):
    is_public: bool = False


class ActionDocument(Record):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    action_code: str
    created_by: RecordId
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


class WorkspaceActionsDocument(Record):
    workspace_id: RecordId
    action_id: RecordId
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
