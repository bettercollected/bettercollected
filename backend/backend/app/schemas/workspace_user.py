import datetime as dt
from typing import List

from beanie import PydanticObjectId

from backend.app.models.enum.workspace_roles import WorkspaceRoles
from common.configs.mongo_document import MongoDocument


class WorkspaceUserDocument(MongoDocument):
    """
    WorkspaceUsers is a subclass of MongoDocument. It represents a
    collection of users in a workspace stored in a MongoDB database.

    Attributes:
        workspace_id (PydanticObjectId): The ID of the workspace.
        userId (PydanticObjectId): The ID of the user.
        roles (List[WorkspaceRoles]): A list of roles that the user has in the
            workspace. Defaults to ["FORM_CREATOR"].

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for
                specific data types.
    """

    workspace_id: PydanticObjectId
    user_id: PydanticObjectId
    roles: List[WorkspaceRoles] = []
    disabled: bool = False

    class Settings:
        name = "workspace_users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
