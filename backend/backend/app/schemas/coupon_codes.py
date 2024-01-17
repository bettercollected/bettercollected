import datetime as dt
from typing import Optional

from beanie import PydanticObjectId, Indexed
from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.types.coupon_code import CouponCode


@entity
class CouponCodeDocument(MongoDocument):
    code: Indexed(CouponCode, unique=True)
    status: CouponStatus = CouponStatus.ACTIVE
    used_by: Optional[PydanticObjectId]

    class Settings:
        name = "coupon_codes"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
