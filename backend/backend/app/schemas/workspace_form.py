import datetime as dt
from typing import Optional

from backend.app.models.enum.update_status import UpdateStatus
from backend.app.models.workspace import WorkspaceFormSettings
from common.records import Record, RecordId

# One link per workspace and form: the unique index of app revision 0019.


class WorkspaceFormDocument(Record):
    """
    WorkspaceForms is a subclass of MongoDocument. It represents a
    collection of forms in a workspace stored in a MongoDB database.

    Attributes:
        workspace_id (PydanticObjectId): The ID of the workspace.
        form_id (str): The ID of the form.
        settings (WorkspaceFormSettings): The settings for the form in the workspace.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    workspace_id: RecordId
    form_id: str
    user_id: str
    settings: Optional[WorkspaceFormSettings] = None
    last_update_status: Optional[UpdateStatus] = None

    class Settings:
        name = "workspace_forms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
