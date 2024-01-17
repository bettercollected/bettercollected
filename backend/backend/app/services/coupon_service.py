from backend.app.models.types.coupon_code import CouponCode
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.schemas.coupon_codes import CouponCodeDocument


class CouponService:

    def __init__(self, coupon_repository: CouponRepository):
        self.coupon_repository = coupon_repository

    async def create_coupons(self, count: int):
        coupons = [CouponCodeDocument(code=CouponCode()) for _ in range(count)]
        return await self.coupon_repository.create_coupons(coupons=coupons)

    async def get_all_coupons(self):
        return await self.coupon_repository.get_all_coupons()
