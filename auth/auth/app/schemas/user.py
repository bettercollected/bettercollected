import datetime as dt
from typing import List, Optional, Annotated

from beanie import Indexed
from common.configs.mongo_document import MongoDocument
from common.enums.plan import Plans



from auth.app.services.database_service import entity


@entity
class UserDocument(MongoDocument):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image: Optional[str] = None
    email: Annotated[str, Indexed(unique=True)]
    roles: Optional[List[str]] = []
    otp_code: Optional[str] = None
    otp_expiry: Optional[int] = None
    otp_code_for: Optional[str] = None
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str] = None
    stripe_payment_id: Optional[str] = None
    last_logged_in: Optional[dt.datetime] = None

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
