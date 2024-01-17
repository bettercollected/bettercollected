from typing import List

from classy_fastapi import Routable, get, post
from common.models.user import User
from fastapi import Depends

from backend.app.container import container
from backend.app.models.types.coupon_code import CouponCode
from backend.app.router import router
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.services.coupon_service import CouponService
from backend.app.services.user_service import get_logged_admin, get_logged_user


@router(prefix="/coupons", tags=["Coupons"])
class CouponController(Routable):

    def __init__(self, coupon_service: CouponService = container.coupon_service(), *args, **kwargs):
        self.coupon_service: CouponService = coupon_service
        super().__init__(*args, **kwargs)

    @get("", response_model=List[CouponCodeDocument])
    async def get_all_coupon_codes(self, user: User = Depends(get_logged_admin)):
        return await self.coupon_service.get_all_coupons()

    @post("/redeem/{coupon_code}")
    async def redeem_coupon(self, coupon_code: CouponCode, user: User = Depends(get_logged_user)):
        return coupon_code

    @post("")
    async def create_coupon_codes(self, count: int = 10, user: User = Depends(get_logged_admin)):
        return await self.coupon_service.create_coupons(count=count)
