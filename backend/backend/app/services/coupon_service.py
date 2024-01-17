from http import HTTPStatus

from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.types.coupon_code import CouponCode
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.services.auth_service import AuthService
from backend.app.services.workspace_service import WorkspaceService


class CouponService:

    def __init__(self, coupon_repository: CouponRepository, auth_service: AuthService,
                 workspace_service: WorkspaceService):
        self.coupon_repository = coupon_repository
        self.auth_service: AuthService = auth_service
        self.workspace_service: WorkspaceService = workspace_service

    async def create_coupons(self, count: int):
        coupons = [CouponCodeDocument(code=CouponCode()) for _ in range(count)]
        return await self.coupon_repository.create_coupons(coupons=coupons)

    async def get_all_coupons(self):
        return await self.coupon_repository.get_all_coupons()

    async def redeem_coupon(self, coupon_code: CouponCode, user: User):
        coupon_document = await self.coupon_repository.get_coupon_by_code(coupon_code=coupon_code)
        if coupon_document.status != CouponStatus.ACTIVE:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, content="Invalid coupon code")
        await self.auth_service.upgrade_user_to_pro(user=user)
        await self.workspace_service.upgrade_user_workspace(user_id=user.id)
        coupon_document.status = CouponStatus.USED
        coupon_document.used_by = user.id
        await coupon_document.save()
