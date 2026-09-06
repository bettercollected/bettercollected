from typing import List

from backend.app.models.types.coupon_code import CouponCode
from backend.app.schemas.coupon_codes import CouponCodeDocument
from common.db.routing import write_op


class CouponRepository:
    @write_op
    async def create_coupons(self, coupons: List[CouponCodeDocument]):
        await CouponCodeDocument.insert_many(coupons)
        return "Created"

    @write_op
    async def save(self, coupon: CouponCodeDocument) -> CouponCodeDocument:
        return await coupon.save()

    async def get_all_coupons(self):
        return await CouponCodeDocument.find().to_list()

    async def get_coupon_by_code(self, coupon_code: CouponCode):
        return await CouponCodeDocument.find_one(CouponCodeDocument.code == coupon_code)
