from typing import Optional
import datetime as dt

from beanie import Indexed

from configs.mongo_document import MongoDocument
from models.workspace import Workspace


class WorkspaceDocument(MongoDocument, Workspace):
    """
    WorkspaceDocument is a subclass of both MongoDocument and Workspace. It represents a collection of workspaces stored
    in a MongoDB database.

    Attributes:
        workspaceName (str): The name of the workspace. This field is indexed and unique.
        customDomain (str, optional): The custom domain of the workspace. This field is indexed.
        default (bool): A flag indicating whether the workspace is the default workspace. Defaults to False.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

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
