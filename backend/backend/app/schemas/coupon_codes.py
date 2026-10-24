import datetime as dt
from typing import Optional

from common.records import Record
from pydantic import EmailStr

from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.types.coupon_code import CouponCode


class CouponCodeDocument(Record):
    # unique in Postgres (app migration 0001)
    code: CouponCode
    status: CouponStatus = CouponStatus.ACTIVE
    used_by: Optional[EmailStr] = None
    activated_at: Optional[dt.datetime] = None

    class Settings:
        name = "coupon_codes"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
