import datetime as dt
from typing import List, Optional, Union

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
        roles (List[WorkspaceRoles | str]): The member's roles. ``[]`` (the
            default, memberships from before roles existed) is an Editor. A
            role this code doesn't know is kept as a string and grants
            nothing (backend.app.services.authorization_service), so a
            membership with a newer role still loads after a rollback.

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
    roles: List[Union[WorkspaceRoles, str]] = []
    disabled: bool = False
    # who created the membership when not an invitation: "sso" (a first
    # single sign-on, just in time) or "scim" (the workspace's directory).
    # A "scim" membership's role and status follow the directory while the
    # workspace has one (docs/sso.md, "Directory sync"); None = by hand.
    provisioned_by: Optional[str] = None

    class Settings:
        name = "workspace_users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
