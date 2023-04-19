import datetime as dt
from typing import List, Optional
from auth.app.services.database_service import entity
from beanie import Indexed
from common.configs.mongo_document import MongoDocument
from common.enums.plan import Plans
from common.enums.roles import Roles


@entity
class UserDocument(MongoDocument):
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image: Optional[str]
    email: Indexed(str, unique=True)
    roles: List[str] = [Roles.FORM_RESPONDER]
    otp_code: Optional[str]
    otp_expiry: Optional[int]
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str]
    stripe_payment_id: Optional[str]

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
