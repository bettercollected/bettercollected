import datetime as dt
import enum

from beanie import PydanticObjectId

from common.configs.mongo_document import MongoDocument


class ResponderGroupDocument(MongoDocument):
    name: str
    workspace_id: PydanticObjectId

    class Settings:
        name = "responder_group"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class ResponderGroupEmailsDocument(MongoDocument):
    group_id: PydanticObjectId
    email: str

    class Settings:
        name = "responder_group_email"
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
