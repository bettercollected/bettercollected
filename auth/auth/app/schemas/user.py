from typing import Optional, List
import datetime as dt

from beanie import Indexed

from auth.app.services.database_service import entity
from common.configs.mongo_document import MongoDocument
from common.enums.form_provider import FormProvider
from common.enums.roles import Roles


@entity
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
    services: Optional[List[FormProvider]]

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
