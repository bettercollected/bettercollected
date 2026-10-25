import datetime as dt
from typing import List, Optional

from common.enums.plan import Plans
from common.records import Record


# An account, stored in auth.users (unique email, indexed Stripe ids: see the
# Alembic migrations). No docstring: it would become the class's JSON schema
# description, which must stay as it was.
class UserDocument(Record):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image: Optional[str] = None
    email: str
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
