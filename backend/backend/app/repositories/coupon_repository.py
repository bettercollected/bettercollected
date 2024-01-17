from typing import List

from backend.app.models.types.coupon_code import CouponCode
from backend.app.schemas.coupon_codes import CouponCodeDocument


class CouponRepository:
    async def create_coupons(self, coupons: List[CouponCodeDocument]):
        await CouponCodeDocument.insert_many(coupons)
        return "Created"

    async def get_all_coupons(self):
        return await CouponCodeDocument.find().to_list()

    async def get_coupon_by_code(self, coupon_code: CouponCode):
        return await CouponCodeDocument.find_one(CouponCodeDocument.code == coupon_code)
