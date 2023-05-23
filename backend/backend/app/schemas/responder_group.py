import datetime as dt
import enum
from typing import Optional

from beanie import PydanticObjectId

from common.configs.mongo_document import MongoDocument


class ResponderGroupDocument(MongoDocument):
    name: str
    workspace_id: PydanticObjectId
    allowed_regex: Optional[str]

    class Settings:
        name = "responder_group"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class IdentifierType(str, enum.Enum):
    EMAIL = "EMAIL"


class ResponderGroupMemberDocument(MongoDocument):
    group_id: PydanticObjectId
    identifier: str
    identifierType: IdentifierType = IdentifierType.EMAIL

    class Settings:
        name = "responder_group_member"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class GroupRoles(str, enum.Enum):
    VIEW = "VIEW"


class ResponderGroupFormDocument(MongoDocument):
    group_id: PydanticObjectId
    form_id: str
    role: GroupRoles = GroupRoles.VIEW

    class Settings:
        name = "responder_group_form"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
