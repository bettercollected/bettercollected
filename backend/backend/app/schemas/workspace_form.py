import datetime as dt
from typing import Optional

from beanie import PydanticObjectId
from pymongo import IndexModel

from backend.app.models.enum.update_status import UpdateStatus
from backend.app.models.workspace import WorkspaceFormSettings
from common.configs.mongo_document import MongoDocument

# One link per workspace and form, as Postgres (app revision 0019). Built at
# startup after Beanie (handlers/database.py), never in the document's
# settings: a database still holding duplicates must start anyway.
#
# Partial on both keys being set (a workspace id, as ObjectId or string, and a
# string form id): a link without one is not indexed, as Postgres treats NULLs
# as distinct. Mongo's planner can't use a partial index for a query that does
# not state that filter, so every read keeps the plan (and the natural order)
# it had without this index; the index only enforces uniqueness.
WORKSPACE_FORM_INDEX_FILTER = {
    "workspace_id": {"$type": ["objectId", "string"]},
    "form_id": {"$type": "string"},
}
WORKSPACE_FORM_INDEX = IndexModel(
    [("workspace_id", 1), ("form_id", 1)],
    unique=True,
    name="uq_workspace_forms_workspace_form",
    partialFilterExpression=WORKSPACE_FORM_INDEX_FILTER,
)


class WorkspaceFormDocument(MongoDocument):
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

    workspace_id: PydanticObjectId
    form_id: str
    user_id: str
    settings: Optional[WorkspaceFormSettings] = None
    last_update_status: Optional[UpdateStatus] = None

    class Settings:
        # No indexes here: the unique link index is built after Beanie, by
        # handlers/database.py (WORKSPACE_FORM_INDEX), so a database still
        # holding duplicate links starts anyway.
        name = "workspace_forms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
