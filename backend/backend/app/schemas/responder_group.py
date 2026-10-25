import datetime as dt
import enum
from typing import Optional

from common.records import Record, RecordId


class ResponderGroupDocument(Record):
    name: Optional[str] = None
    workspace_id: RecordId
    description: Optional[str] = None
    regex: Optional[str] = None

    class Settings:
        name = "responder_group"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class IdentifierType(str, enum.Enum):
    EMAIL = "EMAIL"


class ResponderGroupMemberDocument(Record):
    group_id: RecordId
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


class ResponderGroupFormDocument(Record):
    group_id: RecordId
    form_id: str
    role: GroupRoles = GroupRoles.VIEW

    class Settings:
        name = "responder_group_form"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
