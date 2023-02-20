import calendar
from datetime import datetime, timedelta
from typing import Optional

from beanie import PydanticObjectId
from pymongo import IndexModel

from common.configs.mongo_document import MongoDocument
from common.enums.workspace_invitation_status import InvitationStatus


_time_delta = timedelta()


def _get_expiry_epoch_after(time_delta: timedelta = _time_delta):
    """
    Returns the Unix epoch time of a given time in the future.

    Args:
        time_delta (timedelta, optional): The time in the future to get the Unix epoch for. Defaults to _time_delta.

    Returns:
        int: The Unix epoch time of the given time in the future.
    """
    return calendar.timegm((datetime.utcnow() + time_delta).utctimetuple())


_expiry = _get_expiry_epoch_after()


class WorkspaceUserInvitesDocument(MongoDocument):
    """
    WorkspaceUserInvitesDocument is a subclass of MongoDocument. It represents a collection of user invites for workspaces
    stored in a MongoDB database.

    Attributes:
        workspaceId (PydanticObjectId): The ID of the workspace.
        email (str): The email of the user being invited.
        invitationStatus (InvitationStatus, optional): The status of the invitation. Defaults to InvitationStatus.PENDING.
        expiry (int): The expiration time of the invitation in seconds.
        invitationToken (str): The token for the invitation.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
            indexes (List[IndexModel]): A list of index models for the collection.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    workspaceId: PydanticObjectId
    email: str
    invitationStatus: Optional[InvitationStatus] = InvitationStatus.PENDING
    expiry: int = _expiry
    invitationToken: str

    class Settings:
        name = "workspace_invites"
        indexes = [IndexModel([("workspace_id", 1), ("user_id", 1)], unique=True)]
        bson_encoders = {
            datetime: lambda o: datetime.isoformat(o),
        }
