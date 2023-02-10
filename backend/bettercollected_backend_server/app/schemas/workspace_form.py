import datetime as dt
from beanie import PydanticObjectId

from configs.mongo_document import MongoDocument
from models.workspace import WorkspaceFormSettings


class WorkspaceForms(MongoDocument):
    """
    WorkspaceForms is a subclass of MongoDocument. It represents a collection of forms in a workspace stored in a
    MongoDB database.

    Attributes:
        workspaceId (PydanticObjectId): The ID of the workspace.
        formId (str): The ID of the form.
        settings (WorkspaceFormSettings): The settings for the form in the workspace.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

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
