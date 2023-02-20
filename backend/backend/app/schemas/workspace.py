from typing import Optional
import datetime as dt

from beanie import Indexed

from backend.app.models.workspace import Workspace
from common.configs.mongo_document import MongoDocument


class WorkspaceDocument(MongoDocument, Workspace):
    """
    WorkspaceDocument is a subclass of both MongoDocument and Workspace. It represents a collection of workspaces stored
    in a MongoDB database.

    Attributes:
        workspace_name (str): The name of the workspace. This field is indexed and unique.
        custom_domain (str, optional): The custom domain of the workspace. This field is indexed.
        default (bool): A flag indicating whether the workspace is the default workspace. Defaults to False.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    workspace_name: Indexed(str, unique=True)
    custom_domain: Optional[Indexed(str)]
    default: bool = False

    class Settings:
        name = "workspaces"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
