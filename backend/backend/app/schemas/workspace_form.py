import datetime as dt
from typing import Optional

from beanie import PydanticObjectId
from pymongo import IndexModel

from backend.app.models.enum.update_status import UpdateStatus
from backend.app.models.workspace import WorkspaceFormSettings
from common.configs.mongo_document import MongoDocument


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
        name = "workspace_forms"
        # One link per workspace and form, as Postgres (app revision 0019).
        # Beanie builds it at startup: a database still holding duplicate
        # links refuses to start with a DuplicateKeyError that names this
        # index and one duplicate pair; resolve them by hand first (keep one
        # link per pair; the CHANGELOG entry gives the read-only query).
        # Partial on form_id existing: every link has one, so it holds for all
        # links, and a query that does not name form_id (a workspace's links,
        # a user's imports) can't use it. Those unsorted reads keep returning
        # links in natural (insertion) order, as their Postgres twins order
        # them (created_at, id), so the stores' results stay identical.
        indexes = [
            IndexModel(
                [("workspace_id", 1), ("form_id", 1)],
                unique=True,
                name="uq_workspace_forms_workspace_form",
                partialFilterExpression={"form_id": {"$exists": True}},
            )
        ]
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
