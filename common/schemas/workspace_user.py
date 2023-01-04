import datetime as dt
from typing import List
from beanie import PydanticObjectId

from configs.mongo_document import MongoDocument


class WorkspaceUsers(MongoDocument):
    workspaceId: PydanticObjectId
    userId: PydanticObjectId
    roles: List[str] = ["FORM_CREATOR"]

    class Collection:
        name = "workspaceUsers"

    class Settings:
        name = "workspaceUsers"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
