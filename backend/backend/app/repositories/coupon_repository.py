from typing import List

from backend.app.schemas.coupon_codes import CouponCodeDocument


class CouponRepository:
    async def create_coupons(self, coupons: List[CouponCodeDocument]):
        await CouponCodeDocument.insert_many(coupons)
        return "Created"

    async def get_all_coupons(self):
        return await CouponCodeDocument.find().to_list()

