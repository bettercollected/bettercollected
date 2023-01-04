import datetime as dt
from beanie import PydanticObjectId

from configs.mongo_document import MongoDocument
from models.workspace import WorkspaceFormSettings


class WorkspaceForms(MongoDocument):
    workspaceId: PydanticObjectId
    formId: str
    settings: WorkspaceFormSettings

    class Collection:
        name = "workspaceForms"

    class Settings:
        name = "workspaceForms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
