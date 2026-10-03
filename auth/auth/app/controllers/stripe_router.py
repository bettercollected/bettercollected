from beanie import PydanticObjectId
from fastapi import Body, Depends

from auth.app.container import container
from auth.app.controllers.internal_key import require_internal_key
from auth.app.models.request_dtos import PriceIdRequest
from auth.app.models.response_dtos import PlanResponse
from auth.app.router import router

from classy_fastapi import Routable, get, post

from auth.app.services.stripe_service import StripeService
from auth.config import settings
import stripe

from fastapi import Request, Response


# Per route, not router-level: POST /webhooks stays open (Stripe-signed).
# (classy-fastapi's decorators can't take ``dependencies=``, hence parameters.)
@router(prefix="/stripe")
class StripeRoutes(Routable):
    def __init__(
        self,
        stripe_service: StripeService = container.stripe_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.stripe_service = stripe_service

    @get("/plans")
    async def plans(self, _: None = Depends(require_internal_key)):
        stripe.api_key = settings.stripe_settings.secret
        prices = stripe.Price.list(product=settings.stripe_settings.product_id)
        response = []
        for price in prices.data:
            if price.active:
                response.append(
                    PlanResponse(
                        price.id,
                        price.unit_amount / 100,
                        price.currency,
                        price.recurring.interval,
                    )
                )
        return {"plans": response}

    @get("/session/create/checkout")
    async def checkout(
        self, user_id: str, price_id: str, _: None = Depends(require_internal_key)
    ):
        return await self.stripe_service.create_checkout_session(user_id, price_id)

    @get("/session/create/portal")
    async def customer_portal(
        self, user_id: PydanticObjectId, _: None = Depends(require_internal_key)
    ):
        return await self.stripe_service.create_portal_session(user_id)

    # No internal key: Stripe's signature authenticates it (stripe_service).
    @post("/webhooks")
    async def webhooks(self, request: Request):
        return await self.stripe_service.webhooks(request)
