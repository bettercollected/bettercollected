import calendar
from datetime import datetime, timedelta
from typing import Optional

from beanie import PydanticObjectId
from pymongo import IndexModel

from configs.mongo_document import MongoDocument
from enums.workspace_invitation_status import InvitationStatus


_time_delta = timedelta()


def _get_expiry_epoch_after(time_delta: timedelta = _time_delta):
    return calendar.timegm((datetime.utcnow() + time_delta).utctimetuple())


_expiry = _get_expiry_epoch_after()


class WorkspaceUserInvitesDocument(MongoDocument):
    workspaceId: PydanticObjectId
    email: str
    invitationStatus: Optional[InvitationStatus] = InvitationStatus.PENDING
    expiry: int = _expiry
    invitationToken: str

    class Collection:
        name = "workspaceInvites"
        indexes = [IndexModel([("workspaceId", 1), ("userId", 1)], unique=True)]

    class Settings:
        name = "workspaceInvites"
        bson_encoders = {
            datetime: lambda o: datetime.isoformat(o),
        }
