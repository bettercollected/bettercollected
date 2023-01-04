from typing import Optional
import datetime as dt

from beanie import Indexed

from configs.mongo_document import MongoDocument
from models.workspace import Workspace


class WorkspaceDocument(MongoDocument, Workspace):
    workspaceName: Indexed(str, unique=True)
    customDomain: Optional[Indexed(str)]
    default: bool = False

    class Collection:
        name = "workspace"

    class Settings:
        name = "workspace"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
