import datetime as dt
from typing import List, Optional

from beanie import Indexed

from configs.mongo_document import MongoDocument
from enums.roles import Roles
from models.user import UserConnectedServices


class UserDocument(MongoDocument):
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    email: Indexed(str, unique=True)
    roles: List[str] = [Roles.FORM_RESPONDER]
    otp_code: Optional[str]
    otp_expiry: Optional[int]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    services: Optional[List[UserConnectedServices]]

    class Collection:
        name = "users"

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
