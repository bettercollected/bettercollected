import datetime as dt
from typing import List, Optional

from beanie import Indexed
from common.configs.mongo_document import MongoDocument
from common.enums.plan import Plans

from auth.app.services.database_service import entity


@entity
class UserDocument(MongoDocument):
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image: Optional[str]
    email: Indexed(str, unique=True)
    roles: Optional[List[str]]
    otp_code: Optional[str]
    otp_expiry: Optional[int]
    otp_code_for: Optional[str]
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str]
    stripe_payment_id: Optional[str]
    last_logged_in: Optional[dt.datetime]

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
