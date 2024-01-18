import datetime as dt
from typing import Optional

from beanie import Indexed
from common.configs.mongo_document import MongoDocument
from pydantic import EmailStr

from backend.app.handlers.database import entity
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.types.coupon_code import CouponCode


@entity
class CouponCodeDocument(MongoDocument):
    code: Indexed(CouponCode, unique=True)
    status: CouponStatus = CouponStatus.ACTIVE
    used_by: Optional[EmailStr]
    activated_at: Optional[dt.date]

    class Settings:
        name = "coupon_codes"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
