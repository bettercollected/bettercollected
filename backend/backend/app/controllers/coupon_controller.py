from http import HTTPStatus
from typing import List

from classy_fastapi import Routable, get, post
from common.enums.plan import Plans
from common.models.user import User
from fastapi import Depends
from starlette.responses import Response

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.types.coupon_code import CouponCode
from backend.app.router import router
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.services.auth_cookie_service import set_tokens_to_response
from backend.app.services.coupon_service import CouponService
from backend.app.services.user_service import get_logged_admin, get_logged_user
from backend.config import settings


@router(prefix="/coupons", tags=["Coupons"])
class CouponController(Routable):
    def __init__(
        self,
        coupon_service: CouponService = container.coupon_service(),
        *args,
        **kwargs
    ):
        self.coupon_service: CouponService = coupon_service
        super().__init__(*args, **kwargs)

    @get("", response_model=List[CouponCodeDocument])
    async def get_all_coupon_codes(self, user: User = Depends(get_logged_admin)):
        if not settings.coupon_settings.ENABLED:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Service not enabled",
            )
        return await self.coupon_service.get_all_coupons()

    @post("/redeem/{coupon_code}")
    async def redeem_coupon(
        self,
        coupon_code: CouponCode,
        response: Response,
        user: User = Depends(get_logged_user),
    ):
        if not settings.coupon_settings.ENABLED:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Service not enabled",
            )
        await self.coupon_service.redeem_coupon(coupon_code=coupon_code, user=user)
        user.plan = Plans.PRO
        set_tokens_to_response(user=user, response=response)
        return "Code Redeem Successful"

    @post("")
    async def create_coupon_codes(
        self, count: int = 10, user: User = Depends(get_logged_admin)
    ):
        if not settings.coupon_settings.ENABLED:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Service not enabled",
            )
        return await self.coupon_service.create_coupons(count=count)
