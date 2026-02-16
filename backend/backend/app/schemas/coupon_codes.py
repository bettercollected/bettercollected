import datetime as dt
from typing import Annotated, Optional

from beanie import Indexed
from common.configs.mongo_document import MongoDocument
from pydantic import EmailStr

from backend.app.handlers.database import entity
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.types.coupon_code import CouponCode


@entity
class CouponCodeDocument(MongoDocument):
    code: Annotated[CouponCode, Indexed(unique=True)]
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
